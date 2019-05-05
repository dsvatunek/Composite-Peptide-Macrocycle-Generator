import argparse

from rdkit import Chem
from rdkit.Chem import AllChem, Draw
from tqdm import tqdm

from utils import Database


def merge(template, side_chain):
    """
    Connects the template and side chain together at the designated reacting site (marked by atom map numbers), and
    converts the product to a SMILES string

    Args:
        template (pymongo doc): The template's database document
        side_chain (pymongo doc): The side chains database document

    Returns:
        str: SMILES string reprsenting the product of the template reacting with the side chain
    """

    # convert SMILES strings to mols
    temp = Chem.MolFromSmiles(template['atom_mapped_smiles'])
    sc = Chem.MolFromSmiles(side_chain['atom_mapped_smiles'])

    # get atom map number of reacting site
    temp_map_num = int(template['rxn_ind'])
    sc_map_num = int(side_chain['rxn_ind'])

    # remove substruct and combine mols
    temp = Chem.DeleteSubstructs(temp, Chem.MolFromSmiles(template['substruct']))
    combo = Chem.RWMol(Chem.CombineMols(temp, sc))

    # get reacting atom indicies
    temp_atom = None
    sc_atom = None
    for atom in combo.GetAtoms():
        if atom.GetAtomMapNum() == temp_map_num:
            temp_atom = atom.GetIdx()
        elif atom.GetAtomMapNum() == sc_map_num:
            sc_atom = atom.GetIdx()

    # check if reacting atom is a nitrogen and if so remove all hydrogens
    atom_react = combo.GetAtomWithIdx(sc_atom)
    if atom_react.GetSymbol() == 'N' or atom_react.GetSymbol() == 'O':
        atom_react.SetNumExplicitHs(0)
    elif atom_react.GetSymbol() == 'C' and Chem.Atom.GetTotalNumHs(atom_react) > 0:
        atom_react.SetNumExplicitHs(Chem.Atom.GetTotalNumHs(atom_react) - 1)

    # create bond
    combo.AddBond(temp_atom, sc_atom, order=Chem.rdchem.BondType.SINGLE)
    try:
        Chem.SanitizeMol(combo)
    except:
        print('Error: not a valid SMILES string:', Chem.MolToSmiles(combo))
        print('Temp:', template['atom_mapped_smiles'], '\nside chain:', side_chain['atom_mapped_smiles'])

    return Chem.MolToSmiles(combo)


def generate_rxn_temp(template, side_chain, verbose=False, show=False):
    """
    Uses helper function merge() to generate product SMILES string from connecting the template and side chain together,
    then creates the full reaction template SMARTS string

    Args:
        template (pymongo doc): The template's database document
        side_chain (pumongo doc): The side chain's database document
        verbose (bool, optional): Determines whether to print results to the console. Defaults to False.
        show (bool, optional): Determines whether to show image of reaction template SMARTS. Defaults to False.

    Returns:
        str: The full reaction SMARTS string
    """

    # get SMILES strings
    temp = template['atom_mapped_smiles']
    sc = side_chain['atom_mapped_smiles']
    prod = merge(template, side_chain)

    # combine SMILES strings to get full reaction template SMARTS string
    rxn = '(' + temp + '.' + sc + ')>>' + prod

    if verbose:
        print('SMARTS:', rxn)
        print('Template:', template['name'] + ' :', template['smiles'])
        print('Side Chain:', side_chain['smiles'])

    if show:
        Draw.ReactionToImage(AllChem.ReactionFromSmarts(rxn), subImgSize=(500, 500)).show()

    return rxn


def main():
    parser = argparse.ArgumentParser(description='Generates and stores a SMARTS reaction template based on template '
                                     'and side chain SMILES strings stored in the MongoDB database. The product in the '
                                     'reaction template corresponds to the connection of the template atom with atom '
                                     'map number = 1 to the side chain atom with atom map number = 2. The SMARTS '
                                     'reaction template can then be applied to template-peptide linked molecules to '
                                     'form a macrocycle.')
    parser.add_argument('-t', '--temp', dest='templates', nargs='+', choices=[1, 2, 3, 4], type=int, default=[1],
                        help='Which template(s) SMILES strings to import; 1 - temp1a, 2 - temp1b, 3 - temp2, 4 - temp3')
    parser.add_argument('-d', '--db', dest='database', default='rxn_templates',
                        help='The mongoDB database to connect to')
    parser.add_argument('-hn', '--host', dest='host', default='localhost',
                        help='The host MongoDB server to connect to')
    parser.add_argument('-p', '--port', dest='port', type=int, default=27017,
                        help='The port on host server to connect to')
    parser.add_argument('-s', '--store', dest='store', action='store_false', help='Toggle to not store results')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='Toggle to print reaction SMARTS to console')
    parser.add_argument('-sh', '-show', dest='show', action='store_true',
                        help='Toggle to show reaction SMARTS image; Do not toggle if generating a lot of reaction '
                        'templates')

    args = parser.parse_args()

    # get template names for db querying
    templates = [name for ind, name in enumerate(['temp1a', 'temp1b', 'temp2', 'temp3']) if ind + 1 in args.templates]

    # establish connection and retrieve template and side chain data
    db = Database(host=args.host, port=args.port, db=args.database)
    temp_docs = db.find('templates', {'name': {'$in': templates}})
    sc_docs = db.find_all('side_chains')

    # create SMARTS reaction template between each template and side chain
    for temp in tqdm(temp_docs, desc='Templates: '):
        for sc in tqdm(sc_docs, desc='Side chains: '):
            rxn = generate_rxn_temp(temp, sc, verbose=args.verbose, show=args.show)

            if args.store:
                new_rxn = rxn.replace('\\', '\\\\')
                db.insert_reaction(temp['smiles'], sc['smiles'], new_rxn)


if __name__ == '__main__':
    main()