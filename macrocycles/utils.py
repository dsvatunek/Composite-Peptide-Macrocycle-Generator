import json
from bson import json_util, errors
from rdkit import Chem
import os
import inspect
import logging
from itertools import islice
import logging.handlers
from pymongo import MongoClient, errors
import macrocycles.config as config
from rdkit.Chem import Draw
from pprint import pprint
from macrocycles.exceptions import MergeError


class CustomFormatter(logging.Formatter):
    """
    Formatter for logging. Customizes the exception traceback format.
    """

    def format(self, record):
        """
        Overloaded method for applying custom formats to log records.

        Args:
            record (str): The log record.

        Returns:
            str: The formatted log record.
        """

        result = super(CustomFormatter, self).format(record)
        if record.exc_text:
            result = result.replace('\n', '\n\t')
        return result

    def formatException(self, exc_info):
        """
        Overloaded method for applying custom formats to exception log records.

        Args:
            exc_info (str): The Exception log record.

        Returns:
            str: The exception log record.
        """

        result = super(CustomFormatter, self).formatException(exc_info)
        return result


def create_logger(name, level, path=None):
    """
    Creates a logger with a file handler and CustomFormatter.

    Args:
        name (str): The name of the logger.
        level (int): The level of logs to be recorded by the logger.
        path (str, optional): The path to the log file. Defaults to the LOG_DIR/<caller's name>.log.

    Returns:
        Logger: The logger.
    """

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # set path to log file
    if path is None:
        file = inspect.stack()[-1][1].strip('.py')
        path = os.path.join(config.LOG_DIR, file + '.log')

    # add file handler
    file_handler = logging.handlers.RotatingFileHandler(path, maxBytes=1000000, backupCount=5, encoding='ascii')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = CustomFormatter(
        '[%(asctime)-19s] [%(levelname)-8s] [%(name)s - %(funcName)s - %(lineno)d] -- %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # add console handler
    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setLevel(logging.ERROR)
    # console_formatter = logging.Formatter('%(levelname)s %(name)s - %(message)s')
    # console_handler.setFormatter(console_formatter)
    # logger.addHandler(console_handler)

    return logger


LOGGER = create_logger(name=__name__, level=logging.INFO)

########################################################################################################################
########################################################################################################################
########################################################################################################################


class MongoDataBase():
    """
    A class to establish a connection the Mongo database.
    """

    def __init__(self, settings=config.MONGO_SETTINGS, logger=LOGGER, client=None):
        """
        Constructor - initializes database connection

        Args:
            database (str, optional): The database to connect to. Defaults to 'macrocycles'.
            host (str, optional): The server host name. Defaults to 'localhost'.
            port (int, optional): the port number. Defaults to 27017.
            client (pymongo mongoclient, optional): A pre-initialized pymongo client. Defaults to None.
        """

        try:
            self.logger = logger
            self.client = MongoClient(settings.host, settings.port) if client is None else client
            self.database = self.client[settings.database]
        except (errors.ConnectionFailure, errors.InvalidName, TypeError):
            self.logger.exception(
                f'Settings: host = {settings.host}, port = {settings.port}, database = {settings.database}')
        else:
            self.logger.info(
                f'Established connection to database \'{settings.database}\' with {self.client}')

    def __enter__(self):
        """
        Create object in context manager.
        """

        self.logger.info('Creating instance of MongoDataBase in context manager')
        return self

    def __del__(self):
        """
        Close connection through garbage collection.
        """

        self.client.close()
        self.logger.info(f'Closing connection with {self.client} through garbage collection')

    def __exit__(self, e_type, e_val, traceback):
        """
        Close connection in context manager.
        """

        self.client.close()
        self.logger.info(f'Closing connection with {self.client} through context manager')

    def __getitem__(self, collection):
        """
        Overloaded [] operator. Allows for accessing collections from class instances rather than dereferencing the
        database attribute.

        Args:
            collection (str): The collection to access in the database.

        Returns:
            Collection: An instance of the MongoDB collection.
        """

        try:
            return self.database[collection]
        except (TypeError, errors.InvalidName):
            self.logger.exception(f'Invalid access attempt ([] operator) on {self}')
            raise

    def __repr__(self):
        """
        String representation of the class.
        """

        return f'database \'{self.database.name}\' using \'{self.client}\''

    def setup(self, validation_level='strict', clear=True):
        """
        Set up the database scheme specified in the MongoDataBase section of config.py.

        Args:
            validation_level (str, optional): Set the validation level of each collection. Defaults to 'moderate'.
            clear (bool, optional): If True, clears collections in the database with the same names listed in
                config.COLLECTIONS. Defaults to True.

        Returns:
            bool: True if successful.
        """

        # clear existing collection in database
        if clear:
            self.clear()

        # create collections, add validators and indexes
        for collection, validator, index in zip(config.COLLECTIONS, config.VALIDATORS, config.INDICES):
            try:
                query = {'collMod': collection,
                         'validator': validator,
                         'validationLevel': validation_level}
                self.database.create_collection(collection)
                self.database.command(query)

                # if len(index) > 1:
                #     for ind in index:
                #         self[collection].create_index(ind, unique=True)
                # else:
                #     self[collection].create_index(index, unique=True)

                if index is not None:
                    for ind in index:
                        self[collection].create_index(ind, unique=True)

            except (errors.CollectionInvalid, errors.OperationFailure):
                self.logger.exception(f'Variables: collection = {collection}, schema = {validator}')
                break
            else:
                self.logger.info(
                    f'Created collection \'{collection}\' in database \'{self.database.name}\' and applied index '
                    f'{index} to validation schema {validator}')
        else:
            # intialize records
            self[config.COL4].insert_one({'type': 'parent_side_chain', 'count': 0, 'prefix': ''})
            self[config.COL4].insert_one({'type': 'last_inserted', 'collection': '', 'ids': []})

            self.logger.info('Successfully completed setup()!')
            return True

        return False

    def clear(self):

        try:
            for collection in self.database.list_collection_names():
                self[collection].drop()
                self.logger.info(f'Dropped collection \'{collection}\' from database \'{self.database.name}\'')
        except Exception:
            self.logger.exception('')
            return False

        return True

    # def initialize_counters(self):
    #     self[config.COL4].insert_one({'type': 'parent_side_chain', 'count': 0, 'prefix': ''})
    #     self[config.COL4].insert_one({'type': 'starter_data', 'count': 0, 'prefix': ''})

    def insert(self, collection, docs, ordered=False, create_id=False):
        """
        Insert a document into a collection.

        Args:
            collection (str): The collection to insert the document into.
            document (iterable / dict): Iterable of dictionaries or single dictionary containing the data.

        Returns:
            bool: True if successful
        """

        # convert to list
        if isinstance(docs, dict):
            docs = [docs]

        # give _id if needed
        if create_id:
            docs = self.assign_id(docs)

        try:
            result = self[collection].insert_many(docs, ordered=ordered)
            self[config.COL4].find_one_and_update({'type': 'last_inserted'},
                                                  {'$set': {'collection': collection, 'ids': result.inserted_ids}})
        except (errors.DuplicateKeyError, ValueError, TypeError, errors.InvalidDocument):
            self.logger.exception(f'Failed to save {len(docs)} data points to the Mongo database.')
        except errors.BulkWriteError as err:
            field = 'kekule' if collection == config.COL1 else 'smarts'
            return self.bulkwrite_err_handler(docs, collection, field, err, ordered)
        else:
            self.logger.info(f'Successfully saved {len(docs)} data points to the collection \'{collection}\' on {self}')
            return True

        return False

    def remove_last_insertion(self):

        try:
            doc = self[config.COL4].find_one({'type': 'last_inserted'})
            collection, ids = doc['collection'], doc['ids']

            result = self[collection].delete_many({'_id': {'$in': ids}})
        except ValueError:
            self.logger.exception(f'Failed to delete documents in collection \'{collection}\' with ids {ids}')
        else:
            self.logger.info(f'Successfully deleted {result.deleted_count} documents from collection \'{collection}\'')
            return True

        return False

    def assign_id(self, docs):
        """
        Assigns new IDs to each document in docs.

        Args:
            docs (iterable): An iterable containing the documents to be modified as dictionaries.

        Returns:
            iterable: An iterable containing the modified documents.
        """

        # get latest count and prefixes
        counter = self[config.COL4].find_one({'type': 'parent_side_chain'}, projection={'count': 1, 'prefix': 1})
        count, prefix = counter['count'], counter['prefix']

        # assign _id
        for doc in docs:

            if doc['_id'] is None:
                unique_id, count, prefix = generate_id(count, prefix)
                doc['_id'] = unique_id if doc['type'] == 'parent_side_chain' else unique_id.upper()

        # update count and prefix
        self[config.COL4].find_one_and_update({'type': 'parent_side_chain'},
                                              {'$set': {'count': count, 'prefix': prefix}})
        self.logger.info(
            f'Successfully created {len(docs)} new IDs and updated the count and prefix to {count}, \'{prefix}\'')

        return docs

    def bulkwrite_err_handler(self, docs, collection, field, err, ordered):

        num_docs = len(docs)

        # get _ids, kekule, and messages from documents that caused the error
        err_ids, err_smiles, err_msg, err_op, failed_val, too_large = [], [], [], [], 0, 0
        for error in err.details['writeErrors']:
            if error['code'] == 121:    # document failed validation
                failed_val += 1
            if error['code'] == 17280:  # an index in the document is too large
                too_large += 1
            else:
                err_ids.append(error['op']['_id'])
                err_smiles.append(error['op'][field])
                err_msg.append(error['errmsg'])
                err_op.append(error['op'])

        if failed_val != 0:
            self.logger.error(f'{failed_val}/{num_docs} document failed validation!')
            return False

        if too_large != 0:
            self.logger.error(
                f'{too_large}/{num_docs} documents have too large of a value for an index in the database!')
            return False

        # report error only if duplicate is not a natural amino acid
        count = 0
        for err_doc, msg in zip(err_op, err_msg):
            doc = self[collection].find_one({field: err_doc[field]})
            if doc is None:
                self.logger.error(f'Duplicates exist in the data set you are trying to insert! {err_doc}')
                return False
            if doc['group'] not in ('D-natural', 'L-natural'):
                self.logger.error(f'Failed to save document due to duplicate: {doc}\n{msg}')
                count += 1
            else:
                # doc['side_chain'] = err_doc['side_chain']
                self[collection].update_one({'_id': doc['_id']}, {'$set': {'side_chain': err_doc['side_chain']}})

        # get _ids of successfully inserted documents
        if ordered:
            inserted_ids = [doc['_id'] for doc in docs[:err.details['nInserted']]]
        else:
            all_ids = set(doc['_id'] for doc in docs)
            inserted_ids = list(all_ids.difference(set(err_ids)))

        # update last inserted record
        self[config.COL4].find_one_and_update({'type': 'last_inserted'},
                                              {'$set': {'collection': collection, 'ids': inserted_ids}})

        # report successul or failure
        num_ids = len(inserted_ids)
        if count != 0:
            self.logger.warning(f'{num_ids}/{num_docs} documents were successfully inserted into the '
                                f'database. {count} documents were unexpected duplicates and '
                                f'{num_docs - num_ids - count} documents were duplicates of manually inserted documents'
                                ' (such as natural amino acids)')
            return False

        self.logger.info(f'Successfully inserted {num_ids}/{num_docs} documents into the database. '
                         f'{num_docs - num_ids} documents were duplicates of manually inserted documents '
                         '(such as natural amino acids)')
        return True


def generate_id(count, prefix):
    """
    Method for generating new IDs for parent_side_chains.

    Args:
        count (int): The count stored in the MongoDataBase, which is used for determining the next letter in the ID.
        prefix (str): The prefix to which the next letter in the _id will be appended to.

    Returns:
        str: The new ID.
    """

    aa_codes = 'A R N D C G Q E H I L K M F P S T W Y V'.lower().split(' ')
    alphabet = 'a b c d e f g h i j k l m n o p q r s t u v w x y z'.split(' ')
    code = 'a'

    # find next untaken ID
    while code in aa_codes:
        try:
            code = prefix + alphabet[count]
        except IndexError:
            count = 0
            prefix = set_prefix(prefix)
        else:
            count += 1

    return code, count, prefix


def set_prefix(prefix):
    """
    Recursive method for rotating the prefix letter once they reach 'z'. For example, a prefix 'zz' will turn into
    'aaa'.

    Args:
        prefix (str): The prefix to be rotated.

    Returns:
        str: The rotated prefix.
    """

    # initial prefix assignment
    if prefix == '':
        prefix = 'a'
        return prefix

    # increment last letter of prefix and recursively wrap if necessary
    ending = ord(prefix[-1]) + 1
    if ending > ord('z'):
        prefix = set_prefix(prefix[:-1]) if len(prefix) > 1 else 'a'
        prefix = prefix + 'a'
        return prefix

    # no recursive wrapping needed
    prefix = prefix[:-1] + str(chr(ending))
    return prefix

########################################################################################################################
########################################################################################################################
########################################################################################################################


class Base():
    """
    Class from which all other classes in package will inherit from. Handles data I/O.

    Attributes:
        project_dir: The filepath to the root project directory.
        data_dir: The filepath to the data directory.
        mongo_db: A connection to the MongoDB where the result_data will be stored.
        logger: The logger of the child classes' module.
        result_data: A list to contain the result_data.
    """

    def __init__(self, logger, make_db_connection):
        """
        Constructor.

        Args:
            logger (Logger): The logger to be used by this class.
        """

        # I/O
        self.mongo_db = MongoDataBase(logger=logger) if make_db_connection else None
        self.logger = logger

        # data
        self.result_data = []

    def to_mongo(self, collection, ordered=False, create_id=False):

        return self.mongo_db.insert(collection, self.result_data, ordered=ordered, create_id=create_id)

    def from_mongo(self, collection, query, projection=None):
        """
        Queries the collection in the database defined by self.mongo_db and retrieves the documents whose 'type' field
        equals taht of doc_type.

        Args:
            input_col (str): The name of the collection.
            doc_type (str): The value of the 'type' field of the documents to retrieve.

        Returns:
            pymongo cursor: The cursor containing the data.
        """

        try:
            data = self.mongo_db[collection].find(query, projection)
        except TypeError:
            self.logger.exception(f'Failed to load the data in collection \'{collection}\' on {self.mongo_db}')
        else:
            self.logger.info(f'Successfully loaded {data.count()} data points from collection \'{collection}\' on '
                             f'{self.mongo_db}')
            return data

        return None

    @staticmethod
    def merge(*mols, ignored_map_nums=[], stereo=None, clear_map_nums=True):
        """
        Static method for merging two molecules at the specified atoms, and updating the hydrogen counts as needed. Atom
        map numbers should not be the same for both molecules.

        Args:
            mol1 (rdkit Mol): The molecule to be combined with mol2.
            mol2 (rdkit Mol): The molecule to be combined with mol1.
            map_num1 (int): The atom map number of the atom on mol1 that will form a bond with mol2.
            map_num2 (int): The atom map number of the atom on mol2 that will form a bond with mol1.

        Returns:
            rdkit Mol: The resulting molecule from combining mol1 and mol2 at the specified atoms.
        """

        if len(mols) < 1 or len(mols) > 2:
            raise MergeError('Can only merge 1 or 2 molecules at a time.')

        # find atoms that will form a bond together and update hydrogen counts
        combo, *mols = mols
        for mol in mols:
            combo = Chem.CombineMols(combo, mol)

        # find atoms that will form a bond together and update hydrogen counts
        combo = Chem.RWMol(combo)
        Chem.SanitizeMol(combo)
        try:
            atom1, atom2 = [Base.update_hydrogen_counts(atom, clear_map_nums)
                            for atom in combo.GetAtoms() if atom.GetAtomMapNum() and atom.GetAtomMapNum() not in ignored_map_nums]
        except ValueError:
            raise MergeError('There must be exactly 2 map numbers across all molecules.')

        # create bond, remove hydrogens, and sanitize
        combo.AddBond(atom1.GetIdx(), atom2.GetIdx(), order=Chem.rdchem.BondType.SINGLE)
        Chem.rdmolops.RemoveHs(combo)
        Chem.SanitizeMol(combo)

        # add stereochemistry as specified
        stereo_center = atom1 if atom1.GetHybridization() == Chem.rdchem.HybridizationType.SP3 and \
            atom1.GetTotalNumHs() != 2 else atom2
        if stereo == 'CCW':
            stereo_center.SetChiralTag(Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CCW)
        elif stereo == 'CW':
            stereo_center.SetChiralTag(Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CW)

        return Chem.MolFromSmiles(Chem.MolToSmiles(combo))

    @staticmethod
    def update_hydrogen_counts(atom, clear_map_nums):
        """
        Inner method for clearing the atom map number and updating hydrogen counts.

        Args:
            atom (rdkit Atom): The atom from a molecule that is going to form a bond with an atom from another
                molecule.

        Returns:
            rdkit Atom: The reformatted atom.
        """

        if clear_map_nums:
            atom.SetAtomMapNum(0)

        if atom.GetSymbol() in ['N', 'O', 'S']:
            atom.SetNumExplicitHs(0)
        elif atom.GetSymbol() == 'C' and atom.GetNumExplicitHs() != 0:
            atom.SetNumExplicitHs(atom.GetTotalNumHs() - 1)

        return atom


def read_mols(filepath=None, verbose=False):
    """
    Reads in the molecules defined by the sdf file in filepath.

    Args:
        filepath (str, optional): The filepath to the sdf file to be read. Defaults to None.
        verbose (bool, optional): If True, prints the molecules' SMILES strings to the console. Defaults to False.

    Returns:
        iterable: An iterable containing rdkit Mols.
    """

    # set default
    if filepath is None:
        filepath = os.path.join(config.DATA_DIR, 'chemdraw', 'test_rxn.sdf')

    mols = Chem.SDMolSupplier(filepath)

    # print smiles
    if verbose:
        for mol in mols:
            print(Chem.MolToSmiles(mol))

    return mols


def write_mol(mol, filepath, conf_id=None):
    if filepath.split('.')[-1] != 'sdf':
        print('Error needs to be sdf file')

    writer = Chem.SDWriter(filepath)
    if conf_id is None:
        writer.write(mol)
    elif conf_id == -1:
        for conf in mol.GetConformers():
            writer.write(mol, confId=conf.GetId())
    else:
        writer.write(mol, confId=conf_id)
    writer.close()

    return True


def get_user_approval(question):

    while True:
        answer = input(question)

        if answer in ('y', 'yes'):
            return True

        if answer in ('n', 'no'):
            return False

        print('Please enter either \'y\' or \'n\'')


def get_user_atom_idx(mol, question):

    Draw.ShowMol(mol, includeAtomNumbers=True)
    idxs = set(atom.GetIdx() for atom in mol.GetAtoms())
    while True:
        try:
            atom_idx = int(input(question))
        except ValueError:
            print('Index must be a digit!')
            continue

        if atom_idx in idxs:
            return atom_idx

        print('Index out of range!')


def atom_to_wildcard(atom):
    atom.SetAtomicNum(0)
    atom.SetIsotope(0)
    atom.SetFormalCharge(0)
    atom.SetIsAromatic(False)
    atom.SetNumExplicitHs(0)


def ranges(total, chunks):
    step = total / chunks
    return [(round(step*i), round(step*(i+1))) for i in range(chunks)]


def window(iterable, window_size):
    "Returns a sliding window (of width n) over data from the iterable"
    "   s -> (s0,s1,...s[n-1]), (s1,s2,...,sn), ...                   "
    it = iter(iterable)
    result = tuple(islice(it, window_size))
    if len(result) == window_size:
        yield result
    for elem in it:
        result = result[1:] + (elem,)
        yield result