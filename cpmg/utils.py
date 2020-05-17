import numpy as np
from rdkit import Chem
from types import GeneratorType


def split(data, pred):
    """
    https://stackoverflow.com/questions/8793772/how-to-split-a-sequence-according-to-a-predicate
    """

    yes, no = [], []
    for d in data:
        if pred(d):
            yes.append(d)
        else:
            no.append(d)

    return [yes, no]


def get_maximum(data, func):
    try:
        return np.max(list(map(func, data)))
    except ValueError:
        return None


def to_list(data):
    if isinstance(data, (list, tuple)):
        return data

    if isinstance(data, (GeneratorType, map, filter)):
        return list(data)

    return [data]


def has_atom_map_nums(mol):
    for atom in mol.GetAtoms():
        if atom.GetAtomMapNum() != 0:
            return True

    return False


def get_atom_map_nums(mol):
    atom_map_nums = []
    for atom in mol.GetAtoms():
        map_num = atom.GetAtomMapNum()
        if map_num != 0:
            atom_map_nums.append((atom.GetIdx(), map_num))

    return atom_map_nums


def clear_atom_map_nums(mol):
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)


def clear_isotopes(mol):
    for atom in mol.GetAtoms():
        atom.SetIsotope(0)


def get_atom_with_map_num(mol, map_num):
    for atom in mol.GetAtoms():
        if atom.GetAtomMapNum() == map_num:
            return atom

    raise RuntimeError(f'Atom map number {map_num} not present on molecule {Chem.MolToSmiles(mol)}')


def remove_atom(mol, atom_idx):
    mol = Chem.RWMol(mol)
    mol.RemoveAtom(atom_idx)
    return mol


def get_classmembers(module):
    import inspect
    import sys
    return inspect.getmembers(sys.modules[module], inspect.isclass)


def get_module_strings(module):
    def get_module_strings_closure():
        return [member.STRING for _, member in get_classmembers(module) if hasattr(member, 'STRING')]

    return get_module_strings_closure


def get_filtered_classmembers(module, pred):
    return [member for _, member in get_classmembers(module) if pred(member)]


def create_factory_function_closure(module, obj_type):
    def factory_function_closure(string, *args):
        for _, member in get_classmembers(module):
            try:
                if string == member.STRING:
                    return member(*args)
            except AttributeError:
                pass

        raise ValueError(f'Unrecognized {obj_type} string: {string}')

    return factory_function_closure