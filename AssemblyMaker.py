import ifcopenshell
import ifcopenshell.util.element as ue
import ifcopenshell.util.placement as up
from tkinter import *
from tkinter.filedialog import askopenfilename, asksaveasfilename
import os
from PIL import Image, ImageTk


def create_guid():
    return ifcopenshell.guid.new()

class IfcFile():
    #class for manipulating the ifc objects
    def __init__(self, ifc_file):
        self.ifc_data = ifcopenshell.open(ifc_file)
        self.owner_history = self.ifc_data.by_type('IfcOwnerHistory')[0]
        self.elements = self.ifc_data.by_type('IfcElement')
        self.types = self.get_all_types()
        self.parameter_dict = None

    def get_all_types(self):
        get_types = []
        for element in self.elements:
            ifc_type = element.get_info()['type']
            if ifc_type not in get_types:
                get_types.append(ifc_type)
        return get_types

    def get_elements_by_parameter(self, element_type=None, pset=None, parameter=None, value=None):
        if self.parameter_dict is None:
            self.parameter_dict = {'types': {},
                                   'psets': {},
                                   'parameters': {}
                                   }
            for element in self.elements:
                element_guid = element.GlobalId
                ele_type = element.__dict__['type']
                psets = ue.get_psets(element)
                print(element.Name, 'has', len(psets), 'Psets')
                if ele_type not in self.parameter_dict['types'].keys():
                    self.parameter_dict['types'][ele_type] = {'psets': [], 'elements': []}

                for pset, parameters in psets.items():
                    self.parameter_dict['types'][ele_type]['psets'].append(pset)
                    self.parameter_dict['types'][ele_type]['elements'].append(element_guid)
                    if pset not in self.parameter_dict['psets'].keys():
                        self.parameter_dict['psets'][pset] = {'parameters': [], 'elements': []}
                    for para, val in parameters.items():
                        if val != '':
                            self.parameter_dict['psets'][pset]['parameters'].append(para)
                            self.parameter_dict['psets'][pset]['elements'].append(element_guid)
                            if para not in self.parameter_dict['parameters'].keys():
                                self.parameter_dict['parameters'][para] = {'values': {}, 'elements': []}
                            if val not in self.parameter_dict['parameters'][para]['values'].keys():
                                self.parameter_dict['parameters'][para]['values'][val] = [element_guid]
                            else:
                                self.parameter_dict['parameters'][para]['values'][val].append(element_guid)
                                self.parameter_dict['parameters'][para]['elements'].append(element_guid)

        if parameter is not None:
            return self.parameter_dict['parameters'][parameter]
        else:
            return self.parameter_dict

    def create_assemblies_by_parameter(self, parameter_name: str):

        def make_assembly(p_name, elements):
            element_assembly = self.ifc_data.createIfcElementAssembly(
                create_guid(),
                self.owner_history,
                'Assembly',
                None,
                'Assembly_' + p_name,
                None,
                None,
                None,
                None,
                'NOTDEFINED'
            )
            self.ifc_data.createIfcRelAggregates(
                create_guid(),
                self.owner_history,
                None,
                None,
                element_assembly,
                elements
            )

            try:
                storey = ue.get_container(elements[0])
                storey.ContainsElements[0].RelatedElements += (element_assembly,)
            except:
                pass #skip if attribute not found in class

        found_elements = self.get_elements_by_parameter(parameter_name)
        for assembly, assembly_elements in found_elements.items():
            print(assembly, 'has', len(assembly_elements), 'elements')
            make_assembly(assembly, assembly_elements)


class MasterWindow(Frame):
    #class for the GUI
    def __init__(self):
        Frame.__init__(self)
        #self.master.geometry('300x300')
        self.master.title('BIMnerds IfcElementAssembly Maker')
        self.master.rowconfigure([0, 1, 2, 3, 4, 5, 6], weight=1)
        self.master.columnconfigure(0, weight=3)
        self.master.columnconfigure(1, weight=1)
        self.grid(sticky=W + E + N + S)
        self.ifc_button = Button(self.master, text='Select IFC file', command=self.select_ifc_file).grid(
            row=0, column=0, columnspan=2, sticky=W + E + N + S, padx=5, pady=5)
        self.strvar_ifc_filename = StringVar()
        self.strvar_ifc_filename.set('[no file selected]')
        self.label_ifc_filename = Label(self.master, textvariable=self.strvar_ifc_filename).grid(
            column=0, row=1, columnspan=2, sticky=W + E + N + S)

    def select_ifc_file(self):
        self.filename = askopenfilename(
            title="Select IFC file",
            filetypes=(("IFC file", "*.ifc"), ("All Files", "*.*"))
        )
        self.ifc = IfcFile(self.filename)
        self.strvar_ifc_filename.set(os.path.basename(self.filename))
        self.strvar_ifc_elements = StringVar()
        self.strvar_ifc_elements.set('number of elements: {}'.format(len(self.ifc.elements)))
        self.label_ifc_elements = Label(self.master, textvariable=self.strvar_ifc_elements).grid(
            column=0, row=2, columnspan=2, sticky=W + E + N + S)
        self.strvar_ifc_types = StringVar()
        self.strvar_ifc_types.set('number of types: {}'.format(len(self.ifc.types)))
        self.label_ifc_types = Label(self.master, textvariable=self.strvar_ifc_types).grid(
            column=0, row=3, columnspan=2, sticky=W + E + N + S)
        self.label_parameter = Label(self.master, text='Parameter').grid(
            row=5, column=0, sticky=W + E + N + S)
        self.entry_var = StringVar()
        self.entry_var.set('Unieke nummer')
        self.entry_parameter = Entry(self.master, textvariable=self.entry_var)
        self.entry_parameter.grid(row=4, column=0, sticky=W + E + N + S, padx=5, pady=5)
        self.button_choose_parameter = Button(self.master, text='Select', command=self.select_parameter).grid(
            row=4, column=1, sticky=W + E + N + S, padx=5, pady=5)
        self.button_make_assembly = Button(self.master, text='Make Assembly', command=self.make_assembly).grid(
            row=5, column=0, columnspan=2, sticky=W + E + N + S, padx=5, pady=5)

    def select_parameter(self):
        def selected_parameters():
            selection = self.list_parameters.curselection()
            selection_list = []
            for i in selection:
                selection_list.append(self.list_parameters.get(i))
            print(selection_list)
            self.entry_var.set(','.join(selection_list))
            self.select_para_window.destroy()
        def filter_parameters():
            pass

        self.select_para_window = Toplevel(self.master)
        self.select_para_window.title('select parameter')
        self.select_para_window.columnconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], weight=1)
        self.select_para_window.rowconfigure(0, weight=1)
        self.select_para_window.rowconfigure(1, weight=8)
        self.select_para_window.rowconfigure(2, weight=1)

        self.lb = {}
        column_counter = 0
        listboxes = list(self.ifc.get_elements_by_parameter().keys())
        for listbox in listboxes:
            self.lb[listbox] = {}
            self.lb[listbox]['label'] = Label(self.select_para_window, text='Select ' + listbox)
            self.lb[listbox]['label'].grid(row=0,column=column_counter, columnspan=2)
            self.lb[listbox]['scrollbar'] = Scrollbar(self.select_para_window)
            self.lb[listbox]['scrollbar'].grid(row=1, column=column_counter + 1, sticky=N + S, pady=10)
            self.lb[listbox]['list'] = Listbox(self.select_para_window, selectmode="multiple", yscrollcommand=self.lb[listbox]['scrollbar'].set)
            self.lb[listbox]['list'].grid(padx=10, pady=10, row=1, column=column_counter)
            _list = list(self.ifc.get_elements_by_parameter()[listbox].keys())
            #_list.remove('elements')
            self.lb[listbox]['list'].insert(0, "[ALL]")
            for item in range(len(_list)):
                self.lb[listbox]['list'].insert(END, _list[item])
                self.lb[listbox]['list'].itemconfig(item)
            self.lb[listbox]['scrollbar'].config(command=self.lb[listbox]['list'].yview)
            column_counter += 3

        self.filterButton = Button(self.select_para_window, text='->', command=filter_parameters)
        self.filterButton.grid(row=1, column=2, padx=2)
        self.closeButton = Button(self.select_para_window, text='Close', command=selected_parameters)
        self.closeButton.grid(row=3, column=0, columnspan=9, padx=30, pady=5)

    def make_assembly(self):
        save_file = asksaveasfilename(title='Save IFC file', defaultextension=".ifc")
        if save_file is None:
            return
        parameters = self.entry_parameter.get()
        if ',' in parameters:
            list_parameters = parameters.split(',')
        else:
            list_parameters = [parameters]
        for parameter in list_parameters:
            self.ifc.create_assemblies_by_parameter(parameter)
        self.ifc.ifc_data.write(save_file)
        print('done')



if __name__ == '__main__':
    MasterWindow().mainloop()
    #ifc = IfcFile('Juun/900 BWK-B.ifc')
    #ifc.create_assemblys_by_parameter('Unieke nummer')
    #ifc.ifc_data.write('test27.ifc')