# editor_materials.py
# GUI básica para editar OCDCpro materials collection.json con validación por classifications.json
# Uso:
#   python editor_materials.py
#   python editor_materials.py --collection materials/collection.json --classifications materials/classifications.json
#
# Requisitos: Python 3.8+ (solo stdlib)

import json
import argparse
import os
import sys
from tkinter import (
    Tk, Frame, Label, Entry, Text, Listbox, Scrollbar, Button, END, BOTH, LEFT, RIGHT,
    Y, X, SINGLE, MULTIPLE, VERTICAL, HORIZONTAL, messagebox, StringVar
)
from tkinter.filedialog import askopenfilename, asksaveasfilename

# -------------------------
# Utilidades JSON
# -------------------------

def load_json(path, expect_list=False, expect_dict=False):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if expect_list and not isinstance(data, list):
        raise ValueError(f"{path} debe ser una lista JSON")
    if expect_dict and not isinstance(data, dict):
        raise ValueError(f"{path} debe ser un objeto JSON")
    return data

def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def to_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]

def list_to_csv(lst):
    return ", ".join(lst)

def csv_to_list(s):
    if not s.strip():
        return []
    return [x.strip() for x in s.split(",") if x.strip()]

# -------------------------
# GUI App
# -------------------------

class MaterialsEditor:
    def __init__(self, master, collection_path, classifications_path):
        self.master = master
        master.title("OCDCpro Materials Editor")

        self.collection_path = collection_path
        self.classifications_path = classifications_path

        self.collection = []
        self.classif = {}
        self.current_index = None  # índice en self.collection

        # Cargar datos
        self.reload_data()

        # ----- Layout base -----
        root = Frame(master)
        root.pack(fill=BOTH, expand=True)

        # Panel izquierdo: lista de materiales
        left = Frame(root, width=280)
        left.pack(side=LEFT, fill=Y)

        Label(left, text="Materials").pack(anchor="w", padx=6, pady=(6, 2))

        self.listbox = Listbox(left, selectmode=SINGLE, exportselection=False, width=40)
        self.listbox.pack(side=LEFT, fill=Y, padx=(6,0), pady=(0,6), expand=False)

        lb_scroll = Scrollbar(left, orient=VERTICAL, command=self.listbox.yview)
        lb_scroll.pack(side=RIGHT, fill=Y, padx=(0,6), pady=(0,6))
        self.listbox.config(yscrollcommand=lb_scroll.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # Botonera izquierda
        btns = Frame(left)
        btns.pack(fill=X, padx=6, pady=(0,6))
        Button(btns, text="New", width=8, command=self.on_new).pack(side=LEFT, padx=(0,6))
        Button(btns, text="Save", width=8, command=self.on_save).pack(side=LEFT, padx=(0,6))
        Button(btns, text="Delete", width=8, command=self.on_delete).pack(side=LEFT, padx=(0,6))
        Button(btns, text="Reload", width=8, command=self.on_reload).pack(side=LEFT)

        # Panel derecho: formulario
        right = Frame(root)
        right.pack(side=LEFT, fill=BOTH, expand=True, padx=(8,8), pady=(6,6))

        # Campos texto simples
        self.var_title = StringVar()
        self.var_url = StringVar()
        self.var_last_checked = StringVar()
        self.var_id = StringVar()
        self.var_pdk = StringVar()  # libre
        self.var_tags = StringVar()  # libre (csv)
        self.var_related = StringVar()  # libre (csv)

        self._row(right, "Title", Entry, var=self.var_title)
        self._row(right, "URL", Entry, var=self.var_url)
        self._row(right, "Last checked (YYYY-MM-DD)", Entry, var=self.var_last_checked)
        self._row(right, "ID", Entry, var=self.var_id)

        # Description (Text grande)
        Label(right, text="Description").pack(anchor="w")
        self.txt_desc = Text(right, height=4)
        self.txt_desc.pack(fill=X, pady=(0,8))

        # Campos por clasificaciones (multi-selección)
        self.lbx_type = self._multi_row(right, "Type", self.classif_values("type"))
        self.lbx_topics = self._multi_row(right, "Topics", self.classif_values("topics"))
        self.lbx_stage = self._multi_row(right, "Workflow Stage", self.classif_values("workflow_stage"))
        self.lbx_format = self._multi_row(right, "Format", self.classif_values("format"))
        self.lbx_audience = self._multi_row(right, "Audience", self.classif_values("audience"))
        self.lbx_license = self._multi_row(right, "License", self.classif_values("license"))
        self.lbx_language = self._multi_row(right, "Language", self.classif_values("language"))

        # Campos libres (no clasificados en classifications.json)
        self._row(right, "PDK (csv)", Entry, var=self.var_pdk)
        self._row(right, "Tags (csv)", Entry, var=self.var_tags)
        self._row(right, "Related handbook (csv)", Entry, var=self.var_related)

        # Llenar lista
        self.refresh_listbox()

    # --- helpers UI ---

    def _row(self, parent, label, widget_cls, var=None):
        f = Frame(parent)
        f.pack(fill=X, pady=(0,8))
        Label(f, text=label, width=28, anchor="w").pack(side=LEFT)
        w = widget_cls(f, textvariable=var)
        w.pack(side=LEFT, fill=X, expand=True)
        return w

    def _multi_row(self, parent, label, options):
        f = Frame(parent)
        f.pack(fill=X, pady=(0,8))
        Label(f, text=label, width=28, anchor="w").pack(side=LEFT)
        lbx = Listbox(f, selectmode=MULTIPLE, exportselection=False, height=5)
        lbx.pack(side=LEFT, fill=X, expand=True)
        scroll = Scrollbar(f, orient=VERTICAL, command=lbx.yview)
        scroll.pack(side=LEFT, fill=Y)
        lbx.config(yscrollcommand=scroll.set)
        for opt in options:
            lbx.insert(END, opt)
        return lbx

    # --- data loading ---

    def reload_data(self):
        try:
            self.classif = load_json(self.classifications_path, expect_dict=True)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer classifications.json:\n{e}")
            self.classif = {}

        try:
            self.collection = load_json(self.collection_path, expect_list=True)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo leer collection.json:\n{e}")
            self.collection = []

    def classif_values(self, key):
        # Devuelve lista ordenada de valores válidos para un facet
        node = self.classif.get(key, {})
        vals = []
        if isinstance(node, dict):
            v = node.get("values", {})
            if isinstance(v, dict):
                vals = sorted(list(v.keys()))
        return vals

    # --- list interactions ---

    def refresh_listbox(self):
        self.listbox.delete(0, END)
        for i, item in enumerate(self.collection):
            title = item.get("title") or "(untitled)"
            self.listbox.insert(END, f"{i:03d} — {title}")
        self.current_index = None
        self.clear_form()

    def on_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            self.current_index = None
            self.clear_form()
            return
        idx = sel[0]
        self.current_index = idx
        self.load_into_form(self.collection[idx])

    def on_new(self):
        self.current_index = None
        self.clear_form()
        self.var_title.set("(new)")

    def on_save(self):
        item = self.collect_from_form()
        if not item:
            return  # errores ya mostrados
        if self.current_index is None:
            # nuevo
            self.collection.append(item)
            self.save_collection()
            self.refresh_listbox()
            self.listbox.select_set(END)
            self.listbox.event_generate("<<ListboxSelect>>")
        else:
            # actualizar
            self.collection[self.current_index] = item
            self.save_collection()
            self.refresh_listbox()
            self.listbox.select_set(self.current_index)
            self.listbox.event_generate("<<ListboxSelect>>")

    def on_delete(self):
        if self.current_index is None:
            messagebox.showinfo("Info", "No hay elemento seleccionado.")
            return
        title = self.collection[self.current_index].get("title", "(untitled)")
        if messagebox.askyesno("Confirmar", f"¿Eliminar \"{title}\"?"):
            self.collection.pop(self.current_index)
            self.save_collection()
            self.refresh_listbox()

    def on_reload(self):
        self.reload_data()
        # Re-crear listas de opciones por si cambiaron clasificaciones
        for lbx, key in [
            (self.lbx_type, "type"),
            (self.lbx_topics, "topics"),
            (self.lbx_stage, "workflow_stage"),
            (self.lbx_format, "format"),
            (self.lbx_audience, "audience"),
            (self.lbx_license, "license"),
            (self.lbx_language, "language"),
        ]:
            self._reload_lbx_options(lbx, self.classif_values(key))
        self.refresh_listbox()

    def _reload_lbx_options(self, lbx, options):
        lbx.delete(0, END)
        for opt in options:
            lbx.insert(END, opt)

    # --- form helpers ---

    def clear_form(self):
        self.var_title.set("")
        self.var_url.set("")
        self.var_last_checked.set("")
        self.var_id.set("")
        self.txt_desc.delete("1.0", END)
        self._clear_multis()
        self.var_pdk.set("")
        self.var_tags.set("")
        self.var_related.set("")

    def _clear_multis(self):
        for lbx in [
            self.lbx_type, self.lbx_topics, self.lbx_stage, self.lbx_format,
            self.lbx_audience, self.lbx_license, self.lbx_language
        ]:
            lbx.selection_clear(0, END)

    def _set_multi_selection(self, lbx, values):
        # Selecciona índices cuyo texto esté en values
        values = set(values)
        for i in range(lbx.size()):
            if lbx.get(i) in values:
                lbx.selection_set(i)

    def _get_multi_selection(self, lbx):
        return [lbx.get(i) for i in lbx.curselection()]

    def load_into_form(self, item):
        self.var_title.set(item.get("title", ""))
        self.var_url.set(item.get("url", ""))
        self.var_last_checked.set(item.get("last_checked", ""))
        self.var_id.set(item.get("id", ""))

        self.txt_desc.delete("1.0", END)
        self.txt_desc.insert("1.0", item.get("description", ""))

        self._clear_multis()
        self._set_multi_selection(self.lbx_type, to_list(item.get("type")))
        self._set_multi_selection(self.lbx_topics, to_list(item.get("topics")))
        self._set_multi_selection(self.lbx_stage, to_list(item.get("workflow_stage")))
        self._set_multi_selection(self.lbx_format, to_list(item.get("format")))
        self._set_multi_selection(self.lbx_audience, to_list(item.get("audience")))
        self._set_multi_selection(self.lbx_license, to_list(item.get("license")))
        self._set_multi_selection(self.lbx_language, to_list(item.get("language")))

        self.var_pdk.set(list_to_csv(to_list(item.get("pdk"))))
        self.var_tags.set(list_to_csv(to_list(item.get("tags"))))
        self.var_related.set(list_to_csv(to_list(item.get("related_handbook"))))

    def collect_from_form(self):
        title = self.var_title.get().strip()
        if not title:
            messagebox.showerror("Error", "Title es obligatorio.")
            return None

        # Recoger campos
        obj = {
            "id": self.var_id.get().strip(),
            "title": title,
            "description": self.txt_desc.get("1.0", END).strip(),
            "type": self._get_multi_selection(self.lbx_type),
            "topics": self._get_multi_selection(self.lbx_topics),
            "workflow_stage": self._get_multi_selection(self.lbx_stage),
            "format": self._get_multi_selection(self.lbx_format),
            "audience": self._get_multi_selection(self.lbx_audience),
            "license": self._get_multi_selection(self.lbx_license),
            "language": self._get_multi_selection(self.lbx_language),
            "url": self.var_url.get().strip(),
            "pdk": csv_to_list(self.var_pdk.get()),
            "last_checked": self.var_last_checked.get().strip(),
            "related_handbook": csv_to_list(self.var_related.get()),
            "tags": csv_to_list(self.var_tags.get()),
        }

        # Normalizar vacíos a tipos esperados
        if not obj["id"]:
            obj["id"] = ""  # el usuario dijo que puede quedar vacío
        if not obj["description"]:
            obj["description"] = ""
        if not obj["license"]:
            obj["license"] = ""  # en tu JSON puede venir como string vacío
        if not obj["url"]:
            obj["url"] = ""
        if not obj["last_checked"]:
            obj["last_checked"] = ""

        # Validación dura contra classifications.json (solo para claves presentes allí)
        errors = self.validate_against_classifications(obj)
        if errors:
            messagebox.showerror("Clasificación inválida", "\n".join(errors))
            return None

        return obj

    def validate_against_classifications(self, obj):
        errors = []
        # Para cada facet definido en classifications.json, impedir valores fuera de lista
        def check(key):
            allowed = set(self.classif_values(key))
            vals = set(to_list(obj.get(key)))
            # Permitimos vacío; rechazamos valores no incluidos
            invalid = [v for v in vals if v and v not in allowed]
            if invalid:
                errors.append(f"{key}: {', '.join(invalid)} no está(n) en classifications.json")
        for facet in ["type", "topics", "workflow_stage", "format", "audience", "license", "language"]:
            check(facet)
        return errors

    def save_collection(self):
        try:
            save_json(self.collection_path, self.collection)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar collection.json:\n{e}")

# -------------------------
# main
# -------------------------

def main():
    parser = argparse.ArgumentParser(description="OCDCpro Materials collection.json editor")
    parser.add_argument("--collection", default="materials/collection.json", help="Ruta a collection.json")
    parser.add_argument("--classifications", default="materials/classifications.json", help="Ruta a classifications.json")
    args = parser.parse_args()

    if not os.path.exists(args.classifications):
        print(f"[!] No existe {args.classifications}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.collection):
        print(f"[!] No existe {args.collection}", file=sys.stderr)
        sys.exit(1)

    root = Tk()
    app = MaterialsEditor(root, args.collection, args.classifications)
    root.geometry("980x720")
    root.mainloop()

if __name__ == "__main__":
    main()
