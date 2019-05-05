import argparse
from itertools import chain
from pathlib import Path
from tqdm import tqdm

from rdkit import Chem
from rdkit.Chem import AllChem, Draw


def get_template(fp_in_t, temp_ind):
    """
    Retrieves the template based on the value of temp_ind passed into the function and passes the template to a
    helper function that modifies it in preparation for merging with peptide

    Args:
        fp_in_t (str): The filepath to the text file containing the template SMILES strings
        temp_ind (int): Index indicating which template to retrieve, 1 - temp1a, 2 - temp1b, 3 - temp2, 4 - temp3

    Returns:
        rdkit Mol: The modified template
    """

    template = None
    org_smiles = None
    with open(fp_in_t, 'r') as f:
        for ind, smiles in enumerate(f.readlines()):
            if ind + 1 == temp_ind:
                org_smiles = smiles
                template = modify_template(Chem.MolFromSmiles(smiles), ind + 1)

    return template, org_smiles


def modify_template(template, ind):
    """
    Helper function of get_template(), which performs a deletion of the substructure corresponding to the leaving
    group upon amide bond foramtion and the assignment of an atom map number to reacting carbon atom

    Args:
        template (rdkit Mol): The rdkit Mol representation of the template
        ind (int): The index that idicates the identity of the template

    Returns:
        rdkit Mol: The modified template
    """

    # TODO: Need to implement same process for templates 2 and 3
    if ind == 1 or ind == 2:    # temp 1a or 1b
        patt1 = Chem.MolFromSmiles('O=C1CCC(=O)N1O')  # succinimide + extra oxygen atom
        patt2 = Chem.MolFromSmarts('[CH]=O')    # carbonyl that will form amide with peptide

    # remove reaction point substruct
    template_mod = AllChem.DeleteSubstructs(template, patt1)

    # find and set template peptide connection point
    matches = template_mod.GetSubstructMatches(patt2, useChirality=False)
    for pairs in matches:
        for atom_idx in pairs:
            atom = Chem.Mol.GetAtomWithIdx(template_mod, atom_idx)
            if atom.GetSymbol() == 'C' and Chem.Atom.GetTotalNumHs(atom) == 1:
                atom.SetAtomMapNum(1)

    return template_mod


def get_peptides(peptide_fp):
    """
    Get the peptides from the filepath peptide_fp

    Args:
        peptide_fp (str): The full filepath to the text file containing the peptide SMILES strings

    Returns:
        generator: A generator object containing all peptide SMILES strings in corresponding text file
    """

    with open(peptide_fp, 'r') as f:
        return f.readlines()


def combine(template, peptide):
    """
    Convert the peptide SMILES string to an rdkit Mol and combine it with the template through an amide linkage and the
    designated reacting site

    Args:
        template (rdkit Mol): The template with pre-set atom map number for reacting atom
        peptide (rdkit Mol): The peptide to be attached to the template

    Returns:
        str: The SMILES string of the molecule resulting from merging the template with the peptide
    """

    # portion of peptide backbone containing n-term
    patt = Chem.MolFromSmarts('NCC(=O)NCC(=O)')

    # find n-term nitrogen and assign atom map number
    matches = peptide.GetSubstructMatches(patt, useChirality=False)
    for pairs in matches:
        for atom_idx in pairs:
            atom = Chem.Mol.GetAtomWithIdx(peptide, atom_idx)
            if atom.GetSymbol() == 'N' and Chem.Atom.GetTotalNumHs(atom) == 2:
                atom.SetAtomMapNum(2)

    # prep for modification
    combo = Chem.RWMol(Chem.CombineMols(peptide, template))

    # get reacting atom's indices in combo mol and remove atom map numbers
    pep_atom = None
    temp_atom = None
    for atom in combo.GetAtoms():
        if atom.GetAtomMapNum() == 1:
            temp_atom = atom.GetIdx()
            atom.SetAtomMapNum(0)
        elif atom.GetAtomMapNum() == 2:
            pep_atom = atom.GetIdx()
            atom.SetAtomMapNum(0)

    # create bond and sanitize
    combo.AddBond(temp_atom, pep_atom, order=Chem.rdchem.BondType.SINGLE)
    Chem.SanitizeMol(combo)

    return Chem.MolToSmiles(combo)


def main():
    parser = argparse.ArgumentParser(description='Connects each peptide defined in the input file to a template and '
                                     'write the resulting molecule to file as a SMILES string')
    parser.add_argument('-t', '--temp', dest='template', choices=[1, 2, 3, 4], type=int, default=[1], nargs='+',
                        help='The template(s) to be used; 1 - temp1a, 2 - temp1b, 3 - temp2, 4 - temp3')
    parser.add_argument('-tin', '--temp_in', dest='temp_in', default='templates.txt',
                        help='The text file containing template SMILES strings')
    parser.add_argument('-pin', '--pep_in', dest='pep_in', default=['length3_all.txt'], nargs='+',
                        help='The text file(s) containing peptide SMILES strings')
    parser.add_argument('-o', '--out', dest='out', default=None, nargs='+',
                        help='The output text file(s) to write the resulting SMILES strings; default will out assign '
                        'file names')
    parser.add_argument('-fit', '--fin_t', dest='fp_in_t', default='smiles/templates',
                        help='The filepath to the template text file relative to the base project directory')
    parser.add_argument('-fip', '--fin_p', dest='fp_in_p', default='smiles/peptides',
                        help='The filepath to the peptide text file(s) relative to the base project directory')
    parser.add_argument('-fo', '--fout', dest='fp_out', default='smiles/template_peptide/c_term',
                        help='The filepath for the output text file relative to the base project directory')

    args = parser.parse_args()

    # if output file(s) specified then check for proper number of specified files
    if args.out is not None:
        num_output = len(args.out)
        num_temp = len(args.template)
        num_pep = len(args.pep_in)
        if num_output != num_temp * num_pep:
            print('Number of output files needs to be equal to number of templates * number of peptide files')
            raise SystemExit

    # get full filepath to input files
    base_path = Path(__file__).resolve().parents[1]
    fp_in_t = str(base_path / args.fp_in_t / args.temp_in)
    fp_in_p = [str(base_path / args.fp_in_p / file) for file in args.pep_in]

    # connect all peptides in each peptide group to each template and write to correct output file
    template_names = ['_temp1a', '_temp1b', '_temp2', '_temp3']
    for i, peptide_fp in tqdm(enumerate(fp_in_p)):
        for j, temp_ind in tqdm(enumerate(args.template)):

            # create output filepath based on template and peptide lengths if output file(s) not specified
            outfile_name = args.pep_in[i].split('_')[0] + template_names[j] + '.txt'
            fp_out = str(base_path / args.fp_out /
                         outfile_name) if args.out is None else str(args.out[i * len(args.template) + j])

            # prep corresponding template and peptides
            template, temp_smiles = get_template(fp_in_t, temp_ind)

            # connect and write to file
            with open(fp_out, 'w') as fout, open(peptide_fp, 'r') as f_pep:
                for line in tqdm(f_pep.readlines()):

                    # extract data
                    line = line.split(',')
                    peptide = line[0]
                    monomers = line[1:]

                    # format data
                    pep_temp_mono_str = ',' + peptide.rstrip() + ',' + temp_smiles.rstrip()
                    for monomer in monomers:
                        pep_temp_mono_str += ',' + monomer.rstrip()

                    fout.write(combine(template, Chem.MolFromSmiles(peptide)) + pep_temp_mono_str)
                    fout.write('\n')


if __name__ == '__main__':
    main()