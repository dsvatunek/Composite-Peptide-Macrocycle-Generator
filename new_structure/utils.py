import exceptions
import os

from rdkit import Chem


def connect_mols(*mols, ignored_map_nums=[], stereo=None, clear_map_nums=True):
    """
    Function for combining either one or two molecules at the positions marked by atom map numbers. If more than two
    atom map numbers are supplied across the molecule(s), then those extra map numbers must be specified in the argument
    ignored_map_nums. This function also applies the specified stereochemistry at the connected position if applicable,
    and can clear the map numbers from the molecule after making the connection if desired.

    Args:
        ignored_map_nums (list, optional): The list of atom map numbers to ignore. Defaults to [].
        stereo (str, optional): The stereochemistry to place on the new connection. Can either be 'CW' or 'CCW'.
            Defaults to None.
        clear_map_nums (bool, optional): Whether to clear atom numbers after making the connection or not.
            Defaults to True.

    Raises:
        exceptions.MergeError: Raised if either no molecules or more than two are provided or there are more than two
            atom map numbers present and not in the ignored_map_nums argument.

    Returns:
        RDKit Mol: The result of connecting the molecule(s) at the specified positions.
    """

    def update_hydrogen_counts(atom, clear_map_nums):
        """
        Inner method for clearing the atom map number and updating hydrogen counts.
        """

        if clear_map_nums:
            atom.SetAtomMapNum(0)

        if atom.GetSymbol() in ['N', 'O', 'S']:
            atom.SetNumExplicitHs(0)
        elif atom.GetSymbol() == 'C' and atom.GetNumExplicitHs() != 0:
            atom.SetNumExplicitHs(atom.GetTotalNumHs() - 1)

        return atom

    if len(mols) < 1 or len(mols) > 2:
        raise exceptions.MergeError('Can only merge 1 or 2 molecules at a time.')

    # find atoms that will form a bond together and update hydrogen counts
    combo, *mols = mols
    for mol in mols:
        combo = Chem.CombineMols(combo, mol)

    # find atoms that will form a bond together and update hydrogen counts
    combo = Chem.RWMol(combo)
    Chem.SanitizeMol(combo)
    try:
        atom1, atom2 = [update_hydrogen_counts(atom, clear_map_nums)
                        for atom in combo.GetAtoms() if atom.GetAtomMapNum() and atom.GetAtomMapNum() not in ignored_map_nums]
    except ValueError:
        raise exceptions.MergeError('There must be exactly 2 map numbers across all molecules.')

    # create bond, remove hydrogens, and sanitize
    combo.AddBond(atom1.GetIdx(), atom2.GetIdx(), order=Chem.BondType.SINGLE)
    Chem.RemoveHs(combo)
    Chem.SanitizeMol(combo)

    # add stereochemistry as specified
    stereo_center = atom1 if atom1.GetHybridization() == Chem.HybridizationType.SP3 and atom1.GetTotalNumHs() != 2 else atom2
    if stereo == 'CCW':
        stereo_center.SetChiralTag(Chem.ChiralType.CHI_TETRAHEDRAL_CCW)
    elif stereo == 'CW':
        stereo_center.SetChiralTag(Chem.ChiralType.CHI_TETRAHEDRAL_CW)

    return Chem.MolFromSmiles(Chem.MolToSmiles(combo))


def file_rotator(filepath):
    """
    Function that takes a filepath and attaches a underscore and a number before its extension to ensure uniqueness of
    the file name given by the filepath.

    Args:
        filepath (str): The path to the file.

    Returns:
        str: The augmented filepath.
    """

    idx = 0
    while True:
        new_fp = attach_file_num(filepath, idx)
        idx += 1
        if not (os.path.exists(new_fp) and os.path.isfile(new_fp)):
            return new_fp


def attach_file_num(filepath, file_num):
    """
    Function that inserts an underscore and the specified file number to the file name given in the filepath.

    Args:
        filepath (str): The filepath containing the file name to augment.
        file_num (int): The nile number to attach to the end of the file name in the filepath.

    Returns:
        str: The augmented filepath.
    """

    new_fp, ext = filepath.split('.')
    new_fp += '_' + str(file_num) + '.' + ext
    return new_fp


def get_file_num_range(filepath):
    """
    Function that scans the last directory in the given filepath for all files with the base file name specified in the
    filepath and determines the range of file numbers appended to the base file name that are already in use.

    Args:
        filepath (str): The path to the file.

    Returns:
        tuple[int]: A tuple of ints where the first argument is 0 and the second is the highest used file number of the
            base file name in the directory.
    """

    low = 0
    high = 0
    while True:
        new_fp = attach_file_num(filepath, high)
        if not (os.path.exists(new_fp) and os.path.isfile(new_fp)):
            return low, high
        high += 1