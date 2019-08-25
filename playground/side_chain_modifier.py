"""
Written by Eric Dang.
github: https://github.com/e-dang
email: edang830@gmail.com
"""

import argparse
import os
import sys
from collections import OrderedDict
from logging import INFO

from rdkit import Chem

from macrocycles.config import (CONN_MAP_NUM, HETERO_MAP_NUM,
                                SCM_DOC_TYPE, SCM_INPUT_DIR, SCM_OUTPUT_DIR, SCM_INPUT_COL, SCM_OUTPUT_COL, CONNECTIONS)
from macrocycles.exceptions import MissingMapNumberError
from macrocycles.utils import (Base, IOPaths, Flags, MongoParams, create_logger, set_flags)

LOGGER = create_logger(name=__name__, level=INFO)


class SideChainModifier(Base):
    """
    Class for attaching varying length alkyl chains / attachment points to side chain. Inherits from Base.

    Attributes:
        parent_side_chains (list): Contains the parent_side_chains and associated data as dictionaries.
        connections (list): Contains the atom mapped SMARTS strings of the alkyl attachment chain and the corresponding
            modification array as a Connections named tuple.
    """

    def __init__(self, logger=LOGGER, input_flags=Flags(False, False, True, False),
                 output_flags=Flags(False, False, False, False), no_db=False, **kwargs):
        """
        Initializer.

        Args:
            input_flags (Flags): A namedtuple containing the flags indicating which format to get input data from.
            output_flags (Flags): A namedtuple containing the flags indicating which format to output data to.
            no_db (bool): If True, ensures that no default connection is made to the database. Defaults to False.
            **kwargs:
                f_in (str): The file name(s) containing the input data, if input data has been specified to be retrieved
                    from a file.
                f_out (str): The file name that the result_data will be written to, if specified to do so.
                mongo_params (MongoParams): A namedtuple containing the collection name(s) and value(s) held within the
                    'type' field of the documents to be retrieved, as well as the output collection name.
                no_db (bool): If True, ensures that no default connection is made to the database.
        """

        # I/O
        f_in = [os.path.join(SCM_INPUT_DIR, file) for file in kwargs['f_in']] if 'f_in' in kwargs else ['']
        f_out = os.path.join(SCM_OUTPUT_DIR, kwargs['f_out']) if 'f_out' in kwargs else ''
        mongo_params = kwargs['mongo_params'] if 'mongo_params' in kwargs else MongoParams(
            SCM_INPUT_COL, SCM_DOC_TYPE, SCM_OUTPUT_COL)
        mongo_params = mongo_params if not no_db else None
        super().__init__(IOPaths(f_in, f_out), mongo_params, LOGGER, input_flags, output_flags)

        # data
        self.parent_side_chains = []
        self.connections = CONNECTIONS

    def load_data(self):
        """
        Overloaded method for loading input data.

        Returns:
            bool: True if successful.
        """

        try:
            self.parent_side_chains = super().load_data()[0]  # should be a single item list, access only item
        except IndexError:
            self.logger.exception('Check MongoParams contains correct number of input_cols and input_types. '
                                  f'self.mongo_params = {self.mongo_params}')
        except Exception:
            self.logger.exception('Unexpected exception occured.')
        else:
            return True

        return False

    def diversify(self):
        """
        Main driver of class functionality. Calls self.alternate_connection_point() on each
        molecule in self.parent_side_chains with each connection type in self.connections and calls
        self.accumulate_mols() on the resulting data.

        Returns:
            bool: True if successful.
        """

        try:
            for doc in self.parent_side_chains:
                unique_mols = {}
                for conn_tup in self.connections:
                    unique_mols.update(self.alternate_connection_point(doc['smiles'], conn_tup))
                self.accumulate_mols(unique_mols, doc)
        except MissingMapNumberError:
            self.logger.exception(f'Connection missing map numbers! connection: {conn_tup.smarts}')
        except Exception:
            self.logger.exception('Unexpected exception occured.')
        else:
            self.logger.info(f'Successfully modified parent side chains into {len(self.result_data)} side chains')
            return True

        return False

    def alternate_connection_point(self, parent_sc, connection_tup):
        """
        Creates a set of new molecules by attaching an alkyl chain (which becomes the attachment point to peptide
        backbone) to every eligble position on the side chain. Eligiblity of an atom is defined as:
            Carbon - Must have 1 or 2 hydrogens
            Nitrogen, Oxygen, Sulfur - Must have > 0 hydrogens

        Args:
            mol (str): The SMILES string of the parent side chain molecule.
            connection_tup (Connections): A namedtuple containing the atom mapped alkyl attachment chain and
                modifications array.

        Raises:
            MissingMapNumberError: If connection is not atom mapped.

        Returns:
            dict: Containing the unique side chain SMILES strings as keys and the corresponding kekule SMILES and
                modifications as values.
        """

        unique_mols = {}
        connection, modification = connection_tup
        connection = Chem.MolFromSmarts(connection)
        parent_sc = Chem.MolFromSmiles(parent_sc)

        # check if connecting atom is atom mapped
        if CONN_MAP_NUM not in [atom.GetAtomMapNum() for atom in connection.GetAtoms()]:
            raise MissingMapNumberError('Need to specifiy connecting atom with atom map number')

        # make attachment at each atom
        for atom in parent_sc.GetAtoms():

            # detetmine atom eligibility
            if (atom.GetSymbol() == 'C' and 0 < atom.GetTotalNumHs() < 3) or \
                    (atom.GetSymbol() in ('N', 'O', 'S') and atom.GetTotalNumHs() != 0):
                atom.SetAtomMapNum(HETERO_MAP_NUM)
            else:
                continue

            # merge parent side chain with conenction and record results
            try:
                side_chain = Base.merge(parent_sc, connection, HETERO_MAP_NUM, CONN_MAP_NUM)
            except ValueError:
                self.logger.exception(f'Sanitize error! Parent Side Chain: {Chem.MolToSmiles(parent_sc)}')
            else:
                atom.SetAtomMapNum(0)
                smiles = Chem.MolToSmiles(side_chain)
                Chem.Kekulize(side_chain)
                unique_mols[smiles] = [Chem.MolToSmiles(side_chain, kekuleSmiles=True), modification]

        return unique_mols

    def accumulate_mols(self, unique_mols, parent):
        """
        Stores all data associated with the modified side chain in a dictionary and appends it to self.result_data.

        Args:
            unique_mols (iterable): Contains the unique SMILES strings of the modified side chain.
            parent (dict): The assocaited data of parent side chain from which the modified side chain was derived.
            modifications (list): A list containing ids of the modifications that were made to the parent side chain.
        """

        for i, (smiles, vals) in enumerate(unique_mols.items()):
            doc = OrderedDict([('ID', parent['ID'] + str(i)),
                               ('type', 'side_chain'),
                               ('smiles', smiles),
                               ('kekule', vals[0]),
                               ('modifications', vals[1]),
                               ('parent', parent)])
            self.result_data.append(doc)


def main():
    """
    Driver function. Parses arguments, constructs class, and performs operations on data.
    """

    parser = argparse.ArgumentParser(description='Creates a unique set of molecules by attaching varying length alkyl '
                                     'chains to all elgible positions on the parent side chain. Alkyl chains include '
                                     'methyl, ethyl, and propyl.')
    parser.add_argument('input', choices=['json', 'txt', 'mongo', 'sql'],
                        help='Specifies the format that the input data is in.')
    parser.add_argument('output', nargs='+', choices=['json', 'txt', 'mongo', 'sql'],
                        help='Specifies what format to output the result data in.')
    parser.add_argument('--f_in', dest='f_in', required='json' in sys.argv or 'txt' in sys.argv,
                        help='The input file relative to default input directory defined in config.py.')
    parser.add_argument('--f_out', dest='f_out', default='side_chains',
                        help='The output file relative to the default output directory defined in config.py.')
    parser.add_argument('--no_db', dest='no_db', action='store_true',
                        help='Turns off default connection that is made to the database.')

    args = parser.parse_args()

    # check for proper file specifications
    if args.input in ['json', 'txt']:
        extension = args.f_in.split('.')[-1]
        if args.input != extension:
            LOGGER.error('File extension of the input file does not match the specified format')
            raise OSError('File extension of the input file does not match the specified format')

    # configure I/O
    input_flags, output_flags = set_flags(args.input, args.output)
    f_in = [args.f_in] if args.input in ['json', 'txt'] else ['']

    # create class and perform operations
    modifier = SideChainModifier(f_in=f_in, f_out=args.f_out, input_flags=input_flags,
                                 output_flags=output_flags, no_db=args.no_db)
    if modifier.load_data() and modifier.diversify():
        return modifier.save_data()

    return False


if __name__ == '__main__':
    main()