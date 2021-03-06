import glob
import os
import uuid
from collections import namedtuple
from copy import deepcopy

from rdkit import Chem

import cpmg.config as config
import cpmg.models as models
import cpmg.repository as repo
import cpmg.utils as utils
from cpmg.exceptions import InvalidPrediction


class JsonImporter:
    def load(self, data_type):

        for filepath in self._assemble_filepaths(data_type):
            for doc in utils.load_json(filepath):
                yield doc

    def _assemble_filepaths(self, data_type):
        return glob.glob(os.path.join(config.IMPORT_DIR, data_type + '*.json'))


class ConnectionImporter:
    def __init__(self, loader):
        self.loader = loader
        self.saver = repo.create_connection_repository()

    def import_data(self, filepath=None):
        data = [models.Connection.from_mol(Chem.MolFromSmiles(connection['kekule']))
                for connection in self.loader.load(filepath or self.saver.TYPE.STRING)]
        return self.saver.save(data)


class BackboneImporter:
    def __init__(self, loader):
        self.loader = loader
        self.saver = repo.create_backbone_repository()

    def import_data(self, filepath=None):
        data = []
        for backbone in self.loader.load(filepath or self.saver.TYPE.STRING):
            backbone['binary'] = Chem.MolFromSmiles(backbone['mapped_kekule']).ToBinary()
            data.append(models.Backbone.from_dict(backbone))

        return self.saver.save(data)


class TemplateImporter:
    def __init__(self, loader):
        self.loader = loader
        self.saver = repo.create_template_repository()

    def import_data(self, filepath=None):
        data = []
        for template in self.loader.load(filepath or self.saver.TYPE.STRING):
            template['binary'] = Chem.MolFromSmiles(template['kekule']).ToBinary()
            data.append(models.Template.from_dict(template))

        return self.saver.save(data)


class SidechainImporter:
    def __init__(self, loader):
        self.connections = set()
        self.loader = loader
        self.saver = repo.create_sidechain_repository()

    def import_data(self, filepath=None):
        self._load_connections()
        self._check_connections()

        data = []
        for sidechain in self.loader.load(filepath or self.saver.TYPE.STRING):
            if sidechain['connection'] not in self.connections:
                print(f'Skipping sidechain with unrecognized connection. Sidechain - {sidechain}')
                continue

            sidechain['binary'] = Chem.MolFromSmiles(sidechain['kekule']).ToBinary()
            sidechain['shared_id'] = str(uuid.uuid4())
            data.append(models.Sidechain.from_dict(sidechain))

        return self.saver.save(data)

    def _load_connections(self):
        for connection in repo.create_connection_repository().load():
            self.connections.add(connection.kekule)

    def _check_connections(self):
        if len(self.connections) == 0:
            raise RuntimeError(
                'No connection molecules were found in the repository! Connections must be imported before sidechains '
                'can be imported.')


class MonomerImporter:

    def __init__(self, loader):
        self.loader = loader
        self.saver = repo.create_monomer_repository()
        self.backbones = {}

    def import_data(self, filepath=None):
        self._load_backbones()
        self._check_backbones()
        mock_sidechain = namedtuple('sidechain', 'shared_id connection')

        data = []
        for monomer in self.loader.load(filepath or self.saver.TYPE.STRING):
            data.append(models.Monomer.from_mol(Chem.MolFromSmiles(
                monomer['kekule']), self._match_backbone(monomer['backbone']), mock_sidechain(None, None), True))

        return self.saver.save(data)

    def _load_backbones(self):
        for backbone in repo.create_backbone_repository().load():
            self.backbones[backbone.kekule] = backbone

    def _check_backbones(self):
        if len(self.backbones) == 0:
            raise RuntimeError(
                'No backbone molecules were found in the repository! Backbones must be imported before '
                'monomers can be imported.')

    def _match_backbone(self, backbone):
        try:
            return self.backbones[backbone]
        except KeyError:
            raise KeyError(f'Unrecognized backbone specified in imported monomers: {backbone}')


class RegioSQMPredictionImporter:

    def __init__(self, solvent='nitromethane', cutoff=3.0):
        self.saver = repo.create_regiosqm_repository()
        self.solvent = solvent
        self.cutoff = cutoff
        self.idx_to_smiles = {}

    def import_data(self, filepath=None):
        self._hash_mols()

        data = []
        for row, text in enumerate(utils.load_csv(filepath or config.REGIOSQM_RESULTS_FILEPATH)):
            if row % 3 == 0:
                idx = text[0]
            elif row % 3 == 1:
                predictions = [int(text[j]) for j in range(0, len(text), 2)]
            else:
                self._check_predictions(idx, predictions)
                data.append(models.RegioSQMPrediction.from_dict({'predictions': predictions,
                                                                 'reacting_mol': self.idx_to_smiles[idx],
                                                                 'solvent': self.solvent,
                                                                 'cutoff': self.cutoff}))
        return self.saver.save(data)

    def _hash_mols(self):
        for line in utils.load_text(config.REGIOSQM_SMILES_FILEPATH):
            idx, smiles = line.split(' ')
            self.idx_to_smiles[idx] = smiles.strip('\n')

    def _check_predictions(self, idx, prediction):
        reacting_mol = Chem.MolFromSmiles(self.idx_to_smiles[idx])
        Chem.Kekulize(reacting_mol)
        for atom_idx in prediction:
            atom = reacting_mol.GetAtomWithIdx(atom_idx)
            if atom.GetSymbol() != 'C' or atom.GetTotalNumHs() <= 0 or not atom.GetIsAromatic():
                raise InvalidPrediction(
                    'RegioSQM predictions must correspond to aromatic carbon atoms with at least one hydrogen.')


class pKaPredictionImporter:
    def __init__(self, solvent='water'):
        self.saver = repo.create_pka_repository()
        self.solvent = solvent

    def import_data(self, filepath=None):

        data = []
        for row in utils.load_text(os.path.join(filepath or config.IMPORT_DIR, 'pkas.txt')):
            smiles, pkas = row.split(';')
            smiles = smiles.strip(' ')
            pkas = list(map(float, pkas.strip('\n').strip(' ').split(',')))

            # atom map numbers can change the ordering of atoms in unpredictable ways, thus we must do this VERY
            # annoying round about way of mapping the predictions to the correct heteroatoms on the sidechains used to
            # create reactions
            mol_w_map_nums = Chem.MolFromSmiles(smiles)
            Chem.Kekulize(mol_w_map_nums)

            mol = deepcopy(mol_w_map_nums)
            utils.clear_atom_map_nums(mol)
            mol = Chem.MolFromSmiles(Chem.MolToSmiles(mol))
            Chem.Kekulize(mol)

            # map atom indexes and pkas to each other in mol_w_map_nums using atom map numbers
            pka_map = {}
            for atom in mol_w_map_nums.GetAtoms():
                map_num = atom.GetAtomMapNum()
                if map_num:
                    pka_map[map_num - 1] = (atom.GetIdx(), pkas[map_num - 1])
            map_list = [pka_map[i] for i in sorted(pka_map)]

            # match the pkas to the heteroatoms on properly ordered sidechain
            for match in mol.GetSubstructMatches(mol_w_map_nums):
                heteroatom_pkas = {str(match[atom_idx]): pka for atom_idx, pka in map_list}

            # check because canonicalization of smiles strings might not be consistent
            self._check_predictions(mol, heteroatom_pkas)

            # format data
            data.append(models.pKaPrediction.from_dict({'predictions': heteroatom_pkas,
                                                        'reacting_mol': Chem.MolToSmiles(mol, kekuleSmiles=True),
                                                        'solvent': self.solvent}))

        return self.saver.save(data)

    def _check_predictions(self, reacting_mol, predictions):
        for atom_idx, _ in predictions.items():
            atom = reacting_mol.GetAtomWithIdx(int(atom_idx))
            if atom.GetSymbol() not in ('N', 'O', 'S') or atom.GetTotalNumHs() <= 0:
                raise InvalidPrediction('pKa predictions must correspond to heteroatoms with at least 1 hydrogen')


class PeptidePlanImporter:
    def __init__(self):
        self.saver = repo.create_peptide_plan_repository()

    def import_data(self, filepath, peptide_length):
        peptide_plan = models.PeptidePlan(peptide_length)

        num_lines_in_file = -1
        for i, line in enumerate(utils.load_text(filepath)):
            combo = tuple(map(int, line.strip('\n').split(',')))
            peptide_plan.add(combo)
            num_lines_in_file = i

        self._validate_peptide_plan(peptide_plan, num_lines_in_file)

        return self.saver.save([peptide_plan])

    def _validate_peptide_plan(self, peptide_plan, num_lines_in_file):
        if len(peptide_plan) != num_lines_in_file + 1:
            raise RuntimeWarning('There was a non-unique combo specified in the imported peptide plan file')


def create_mol_importers(data_format_importer=JsonImporter()):
    return [ConnectionImporter(data_format_importer),
            BackboneImporter(data_format_importer),
            TemplateImporter(data_format_importer),
            SidechainImporter(data_format_importer),
            MonomerImporter(data_format_importer)]


def create_prediction_importers():
    return [RegioSQMPredictionImporter(), pKaPredictionImporter()]


def create_importers(data_format_importer=JsonImporter()):
    return create_mol_importers(data_format_importer) + create_prediction_importers()
