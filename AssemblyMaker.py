import ifcopenshell
import ifcopenshell.util.element as ue
import ifcopenshell.util.placement as up
from tkinter import *
from tkinter.filedialog import askopenfilename, asksaveasfilename
import os
from PIL import Image, ImageTk
import pandas as pd

pd.set_option("display.max_rows", None, "display.max_columns", None, "display.max_colwidth", -1, "display.width", None)


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
        self.element_parameter_table = None

    def get_all_types(self):
        get_types = []
        for element in self.elements:
            ifc_type = element.get_info()['type']
            if ifc_type not in get_types:
                get_types.append(ifc_type)
        return get_types

    def parameter_table(self):

        if self.element_parameter_table is None:

            pandas_dict = {
                'global_id': [],
                'types': [],
                'psets': [],
                'parameters': [],
                'values': [],
            }

            for element in self.elements:
                psets= ue.get_psets(element)
                for pset, parameters in psets.items():
                    for parameter, value in parameters.items():
                        if value != '':
                            pandas_dict['global_id'].append(element.GlobalId)
                            pandas_dict['types'].append(element.__dict__['type'])
                            pandas_dict['psets'].append(pset)
                            pandas_dict['parameters'].append(parameter)
                            pandas_dict['values'].append(value)
            self.element_parameter_table = pd.DataFrame.from_dict(pandas_dict)

        return self.element_parameter_table

    def get_parameter_info(self, parameter=None):
        if self.parameter_dict is None:
            self.parameter_dict = {'types': {},
                                   'psets': {},
                                   'parameters': {}}
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

    def get_elements_by_filter(self, parameters: list, **filters):

        if not isinstance(parameters, list):
            raise TypeError('parameters argument needs to be a list, got {}'.format(type(parameters)))

        agreed_args = list(self.parameter_table().columns)
        for arg in filters.keys():
            if arg not in agreed_args:
                raise KeyError('Can not filter on {arg}, must be of {list}'.format(arg=arg, list=agreed_args))

        filters['parameters'] = parameters
        print(filters)
        conditions = ''
        print(self.parameter_table())
        self.list_to_assemble = {}

        for column, filter_list in filters.items():
            if len(filter_list) > 0:
                conditions = '{column}.isin({list})'.format(column=column, list=filter_list)

                new_df = self.parameter_table().query(conditions)
                unique_values = list(new_df['values'].unique())
                print(unique_values)
                for val in unique_values:
                    self.list_to_assemble[val] = list(new_df.loc[new_df['values'] == val, 'global_id'])
        #conditions = conditions[:-3]
        print(self.list_to_assemble)

        """
        new_df = self.parameter_table().query(conditions)
        for column, filterlist in filters.items():
            if len(filter_list) > 0:
        
        guid_list = list(new_df['global_id'])
        print(guid_list)
        for guid in guid_list:
            element = self.ifc_data.by_guid(guid)
            print(element.Name)
        """

    def make_assembly(self, p_name, elements):
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

    def create_assemblies_by_parameter(self, parameter_name: str):

        found_elements = self.get_parameter_info(parameter_name)
        for assembly, assembly_elements in found_elements.items():
            print(assembly, 'has', len(assembly_elements), 'elements')
            self.make_assembly(assembly, assembly_elements)


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
            answers = {}
            for lb in self.listboxes:
                selection = self.lb[lb]['list'].curselection()
                value_list = [line.strip(' \'') for line in self.lb[lb]['listvar'].get()[1:-1].split(',')]
                answers[lb] = [value_list[index] for index in selection]

            parameters = answers.pop('parameters', None)
            if parameters is None:
                raise KeyError('At least one parameter should be selected')
            elif isinstance(parameters, str):
                parameters = [parameters]
            else:
                self.ifc.get_elements_by_filter(parameters, **answers)

            self.entry_var.set('[SELECTION]')
            self.entry_parameter.config(state='disabled')
            self.select_para_window.destroy()

        def filter_parameters(listbox):
            selection = self.lb[listbox]['list'].curselection()
            value_list = [line.strip(' \'') for line in self.lb[listbox]['listvar'].get()[1:-1].split(',')]
            selected_list = [value_list[index] for index in selection]
            next_listbox = self.listboxes[self.listboxes.index(listbox) + 1]
            new_list = []
            if not selected_list:
                new_list = list(self.ifc.parameter_table()[next_listbox].unique())
            elif selected_list[0] == '[ALL]':
                new_list = list(self.ifc.parameter_table()[next_listbox].unique())
            else:
                new_list = list(self.ifc.parameter_table()[next_listbox].loc[
                    self.ifc.parameter_table()[listbox].isin(selected_list)].unique())

            self.lb[next_listbox]['listvar'].set(value=new_list)


        self.select_para_window = Toplevel(self.master)
        self.select_para_window.title('select parameter')
        self.select_para_window.columnconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], weight=1)
        self.select_para_window.rowconfigure(0, weight=1)
        self.select_para_window.rowconfigure(1, weight=8)
        self.select_para_window.rowconfigure(2, weight=1)

        self.lb = {}
        column_counter = 0
        self.listboxes = list(self.ifc.parameter_table().columns)
        self.listboxes.remove('global_id')
        for listbox in self.listboxes:
            self.lb[listbox] = {}
            self.lb[listbox]['label'] = Label(self.select_para_window, text='Select ' + listbox)
            self.lb[listbox]['label'].grid(row=0, column=column_counter, columnspan=2)
            self.lb[listbox]['scrollbar'] = Scrollbar(self.select_para_window)
            self.lb[listbox]['scrollbar'].grid(row=1, column=column_counter + 1, sticky=N + S, pady=10)
            self.lb[listbox]['listvar'] = StringVar()
            self.lb[listbox]['list'] = Listbox(
                self.select_para_window,
                selectmode="multiple",
                listvariable=self.lb[listbox]['listvar'],
                yscrollcommand=self.lb[listbox]['scrollbar'].set
            )
            self.lb[listbox]['list'].grid(padx=10, pady=10, row=1, column=column_counter, sticky=N + S + E + W)
            _list = list(self.ifc.parameter_table()[listbox].unique())
            _list.insert(0, "[ALL]")
            self.lb[listbox]['listvar'].set(value=_list)

            if listbox != 'values':
                self.lb[listbox]['button'] = Button(self.select_para_window, text='->',
                                                    command=lambda x=listbox: filter_parameters(x))
                self.lb[listbox]['button'].grid(row=1, column=column_counter+2, padx=2)

            column_counter += 3

        self.closeButton = Button(self.select_para_window, text='Apply', command=selected_parameters)
        self.closeButton.grid(row=3, column=0, columnspan=12, padx=30, pady=5)

    def make_assembly(self):
        save_file = asksaveasfilename(title='Save IFC file', defaultextension=".ifc")
        if save_file is None:
            return
        parameters = self.entry_parameter.get()
        if parameters != '[SELECTION]':
            if ',' in parameters:
                list_parameters = parameters.split(',')
            else:
                list_parameters = [parameters]
            for parameter in list_parameters:
                self.ifc.create_assemblies_by_parameter(parameter)
        else:
            for name, element_ids in self.ifc.list_to_assemble.items():
                elements = []
                for element_id in element_ids:
                    elements.append(self.ifc.ifc_data.by_guid(element_id))
                self.ifc.make_assembly(name, elements)
        self.ifc.ifc_data.write(save_file)
        print('done')



if __name__ == '__main__':
    MasterWindow().mainloop()
    #ifc = IfcFile('Juun/900 BWK-B.ifc')
    #ifc.create_assemblys_by_parameter('Unieke nummer')
    #ifc.ifc_data.write('test27.ifc')