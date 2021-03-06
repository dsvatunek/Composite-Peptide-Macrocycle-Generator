from collections import namedtuple
from copy import deepcopy
from itertools import chain
import pprint

from rdkit import Chem
from rdkit.Chem import AllChem

import cpmg.config as config
import cpmg.exceptions as exceptions
import cpmg.utils as utils

METHANE = 'C'
SC_ATTACHMENT_POINT = Chem.MolFromSmarts('[CH3;!13CH3]')  # methyls marked with C13 aren't used as attachment points
METHYL = Chem.MolFromSmarts('[CH3]')
CARBOXYL = Chem.MolFromSmarts('C(=O)[OH]')
N_TERM = Chem.MolFromSmarts('[NH2]')
PROLINE_N_TERM = Chem.MolFromSmarts('[NH;R]')
ALPHA_BACKBONE = Chem.MolFromSmarts('NCC(=O)O')
TAGGED_ALPHA_BACKBONE = Chem.MolFromSmarts('N[CH2:1]C(=O)[OH]')


def print_model(obj_type, obj_dict):
    data = {'type': obj_type}
    data.update(obj_dict)
    data.pop('binary', None)
    return pprint.pformat(data)


class AbstractMolecule:
    def __init__(self, binary, kekule, _id=None):
        self._id = _id
        self.binary = binary
        self.kekule = kekule

    def __key(self):
        return (self.kekule,)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.__key() == other.__key()
        return NotImplemented

    def __repr__(self):
        return print_model(self.STRING, self.__dict__)  # pylint: disable=no-member

    @property
    def mol(self):
        return Chem.Mol(self.binary)

    def to_dict(self):
        data = deepcopy(self.__dict__)
        data.pop('_id')
        return data


class Backbone(AbstractMolecule):
    STRING = 'backbone'
    MAP_NUM = 1

    def __init__(self, binary, kekule, mapped_kekule, _id=None):
        super().__init__(binary, kekule, _id)
        self.mapped_kekule = mapped_kekule

    def __eq__(self, other):
        return super().__eq__(other) and self.mapped_kekule == other.mapped_kekule

    @classmethod
    def from_mol(cls, mol):
        Chem.SanitizeMol(mol)
        cls.validate(mol)
        Chem.Kekulize(mol)
        mapped_kekule = Chem.MolToSmiles(mol, kekuleSmiles=True)
        utils.clear_atom_map_nums(mol)
        return cls(mol.ToBinary(), Chem.MolToSmiles(mol, kekuleSmiles=True), mapped_kekule)

    @classmethod
    def from_dict(cls, data):
        cls.validate(Chem.Mol(data['binary']))
        return cls(data['binary'], data['kekule'], data['mapped_kekule'], _id=data.get('_id', None))

    @staticmethod
    def validate(mol):
        try:
            _, map_nums = zip(*utils.get_atom_map_nums(mol))
            if not all(map(lambda x: x == Backbone.MAP_NUM, map_nums)):
                raise ValueError
        except ValueError:
            raise exceptions.InvalidMolecule(
                f'Backbone molecule is missing an atom map number or the atom map number is not equal to 1')

        return True

    def to_reduced_dict(self):
        data = deepcopy(self.__dict__)
        data.pop('binary')
        data.pop('mapped_kekule')
        return data


class Connection(AbstractMolecule):
    STRING = 'connection'

    def __init__(self, binary, kekule, _id=None):
        super().__init__(binary, kekule, _id)

    @classmethod
    def from_mol(cls, mol):
        Chem.SanitizeMol(mol)
        Chem.Kekulize(mol)
        return cls(mol.ToBinary(), Chem.MolToSmiles(mol, kekuleSmiles=True))

    @classmethod
    def from_dict(cls, data):
        return cls(data['binary'], data['kekule'], _id=data.get('_id', None))


class Template(AbstractMolecule):
    STRING = 'template'

    OLIGOMERIZATION_MAP_NUM = 1
    EAS_MAP_NUM = 200
    WC_MAP_NUM_1 = 201
    WC_MAP_NUM_2 = 202
    PS_OXYGEN_MAP_NUM = 300
    PS_CARBON_MAP_NUM = 301
    TEMPLATE_PS_NITROGEN_MAP_NUM = 302

    def __init__(self, binary, kekule, oligomerization_kekule, friedel_crafts_kekule, tsuji_trost_kekule,
                 pictet_spangler_kekule, template_pictet_spangler_kekule, pyrroloindoline_kekule,
                 aldehyde_cyclization_kekule, _id=None):
        super().__init__(binary, kekule, _id)
        self.oligomerization_kekule = oligomerization_kekule
        self.friedel_crafts_kekule = friedel_crafts_kekule
        self.tsuji_trost_kekule = tsuji_trost_kekule
        self.pictet_spangler_kekule = pictet_spangler_kekule
        self.template_pictet_spangler_kekule = template_pictet_spangler_kekule
        self.pyrroloindoline_kekule = pyrroloindoline_kekule
        self.aldehyde_cyclization_kekule = aldehyde_cyclization_kekule

    @classmethod
    def from_mol(cls, mol, oligomerization_kekule, friedel_crafts_kekule, tsuji_trost_kekule, pictet_spangler_kekule,
                 template_pictet_spangler_kekule, pyrroloindoline_kekule, aldehyde_cyclization_kekule):
        cls.validate({'oligomerization_kekule': oligomerization_kekule,
                      'friedel_crafts_kekule': friedel_crafts_kekule,
                      'tsuji_trost_kekule': tsuji_trost_kekule,
                      'pictet_spangler_kekule': pictet_spangler_kekule,
                      'template_pictet_spangler_kekule': template_pictet_spangler_kekule,
                      'pyrroloindoline_kekule': pyrroloindoline_kekule,
                      'aldehyde_cyclization_kekule': aldehyde_cyclization_kekule})
        Chem.Kekulize(mol)
        return cls(mol.ToBinary(), Chem.MolToSmiles(mol, kekuleSmiles=True), oligomerization_kekule,
                   friedel_crafts_kekule, tsuji_trost_kekule, pictet_spangler_kekule, template_pictet_spangler_kekule,
                   pyrroloindoline_kekule, aldehyde_cyclization_kekule)

    @classmethod
    def from_dict(cls, data):
        cls.validate(data)
        return cls(data['binary'], data['kekule'], data['oligomerization_kekule'], data['friedel_crafts_kekule'],
                   data['tsuji_trost_kekule'], data['pictet_spangler_kekule'], data['template_pictet_spangler_kekule'],
                   data['pyrroloindoline_kekule'], data['aldehyde_cyclization_kekule'], _id=data.get('_id', None))

    @staticmethod
    def validate(data):
        try:
            if data['oligomerization_kekule'] is not None:
                Template.validate_oligomerization_mol(Chem.MolFromSmiles(data['oligomerization_kekule']))
            if data['friedel_crafts_kekule'] is not None:
                Template.validate_friedel_crafts_mol(Chem.MolFromSmiles(data['friedel_crafts_kekule']))
            if data['tsuji_trost_kekule'] is not None:
                Template.validate_tsuji_trost_mol(Chem.MolFromSmiles(data['tsuji_trost_kekule']))
            if data['pictet_spangler_kekule'] is not None:
                Template.validate_pictet_spangler_mol(Chem.MolFromSmiles(data['pictet_spangler_kekule']))
            if data['template_pictet_spangler_kekule'] is not None:
                Template.validate_template_pictet_spangler_mol(
                    Chem.MolFromSmiles(data['template_pictet_spangler_kekule']))
            if data['pyrroloindoline_kekule'] is not None:
                Template.validate_pyrroloindoline_mol(Chem.MolFromSmiles(data['pyrroloindoline_kekule']))
            if data['aldehyde_cyclization_kekule'] is not None:
                Template.validate_aldehyde_cyclization_mol(Chem.MolFromSmiles(data['aldehyde_cyclization_kekule']))
        except ValueError as err:
            raise exceptions.InvalidMolecule(str(err))

        return True

    @staticmethod
    def validate_oligomerization_mol(mol):
        _, map_nums = zip(*utils.get_atom_map_nums(mol))
        if Template.OLIGOMERIZATION_MAP_NUM not in map_nums:
            raise ValueError(f'Template molecule is missing oligomerization atom map number!')

        return True

    @staticmethod
    def validate_friedel_crafts_mol(mol):
        _, map_nums = zip(*utils.get_atom_map_nums(mol))
        if Template.EAS_MAP_NUM not in map_nums or Template.WC_MAP_NUM_1 not in map_nums:
            raise ValueError(f'Template molecule is missing friedel crafts atom map numbers!')

        return True

    @staticmethod
    def validate_tsuji_trost_mol(mol):
        _, map_nums = zip(*utils.get_atom_map_nums(mol))
        if Template.EAS_MAP_NUM not in map_nums or Template.WC_MAP_NUM_1 not in map_nums:
            raise ValueError(f'Template molecule is missing tsuji trost atom map numbers!')

        return True

    @staticmethod
    def validate_pictet_spangler_mol(mol):
        _, map_nums = zip(*utils.get_atom_map_nums(mol))
        if Template.OLIGOMERIZATION_MAP_NUM not in map_nums \
                or Template.WC_MAP_NUM_1 not in map_nums \
                or Template.PS_OXYGEN_MAP_NUM not in map_nums \
                or Template.PS_CARBON_MAP_NUM not in map_nums:
            raise ValueError(f'Template molecule is missing pictet spangler atom map numbers!')

        return True

    @staticmethod
    def validate_template_pictet_spangler_mol(mol):
        _, map_nums = zip(*utils.get_atom_map_nums(mol))
        if Template.EAS_MAP_NUM not in map_nums \
                or Template.WC_MAP_NUM_1 not in map_nums \
                or Template.WC_MAP_NUM_2 not in map_nums \
                or Template.PS_OXYGEN_MAP_NUM not in map_nums \
                or Template.PS_CARBON_MAP_NUM not in map_nums \
                or Template.TEMPLATE_PS_NITROGEN_MAP_NUM not in map_nums:
            raise ValueError(f'Template molecule is missing pictet spangler atom map numbers!')

        return True

    @staticmethod
    def validate_pyrroloindoline_mol(mol):
        _, map_nums = zip(*utils.get_atom_map_nums(mol))
        if Template.EAS_MAP_NUM not in map_nums or Template.WC_MAP_NUM_1 not in map_nums:
            raise ValueError(f'Template molecule is missing pyrroloindoline atom map numbers!')

        return True

    @staticmethod
    def validate_aldehyde_cyclization_mol(mol):
        _, map_nums = zip(*utils.get_atom_map_nums(mol))
        if Template.OLIGOMERIZATION_MAP_NUM not in map_nums \
                or Template.WC_MAP_NUM_1 not in map_nums \
                or Template.PS_OXYGEN_MAP_NUM not in map_nums \
                or Template.PS_CARBON_MAP_NUM not in map_nums:
            raise ValueError(f'Template molecule is missing pictet spangler atom map numbers!')

        return True

    @property
    def oligomerization_mol(self):
        return Chem.MolFromSmiles(self.oligomerization_kekule)

    @property
    def friedel_crafts_mol(self):
        return Chem.MolFromSmiles(self.friedel_crafts_kekule) if self.friedel_crafts_kekule is not None else None

    @property
    def tsuji_trost_mol(self):
        return Chem.MolFromSmiles(self.tsuji_trost_kekule) if self.tsuji_trost_kekule is not None else None

    @property
    def pictet_spangler_mol(self):
        return Chem.MolFromSmiles(self.pictet_spangler_kekule) if self.pictet_spangler_kekule is not None else None

    @property
    def template_pictet_spangler_mol(self):
        return Chem.MolFromSmiles(self.template_pictet_spangler_kekule) if self.template_pictet_spangler_kekule is not None else None

    @property
    def pyrroloindoline_mol(self):
        return Chem.MolFromSmiles(self.pyrroloindoline_kekule) if self.pyrroloindoline_kekule is not None else None

    @property
    def aldehyde_cyclization_mol(self):
        return Chem.MolFromSmiles(self.aldehyde_cyclization_kekule) if self.aldehyde_cyclization_kekule is not None else None


class Sidechain(AbstractMolecule):
    STRING = 'sidechain'
    MAP_NUM = 2

    def __init__(self, binary, kekule, attachment_point, connection, shared_id, _id=None):
        super().__init__(binary, kekule, _id)
        self.attachment_point = attachment_point
        self.connection = connection
        self.shared_id = shared_id

    def __eq__(self, other):
        return self.kekule == other.kekule and self.connection == other.connection and self.shared_id == other.shared_id

    @classmethod
    def from_mol(cls, mol, connection, shared_id):
        Chem.SanitizeMol(mol)
        Chem.Kekulize(mol)
        attachment_point = cls.validate(mol)
        return cls(mol.ToBinary(), Chem.MolToSmiles(mol, kekuleSmiles=True), attachment_point, connection.kekule, shared_id)

    @classmethod
    def from_dict(cls, data):
        attachment_point = cls.validate(Chem.Mol(data['binary']))
        return cls(data['binary'], data['kekule'], attachment_point, data['connection'], data['shared_id'], _id=data.get('_id', None))

    @staticmethod
    def validate(mol):
        attachment_point = list(chain.from_iterable(mol.GetSubstructMatches(SC_ATTACHMENT_POINT)))
        if len(attachment_point) != 1:
            raise exceptions.InvalidMolecule(f'Sidechains must have exactly one attachment point')

        return attachment_point[0]

    @property
    def mapped_mol(self):
        sidechain = self.mol
        sidechain.GetAtomWithIdx(self.attachment_point).SetAtomMapNum(self.MAP_NUM)
        return sidechain

    def to_dict(self):
        data = super().to_dict()
        data.pop('attachment_point')
        return data


class Monomer(AbstractMolecule):
    STRING = 'monomer'

    def __init__(self, binary, kekule, required, backbone, sidechain, connection, proline, imported, _id=None, index=None):
        super().__init__(binary, kekule, _id)
        self.index = index
        self.required = required
        self.backbone = backbone
        self.sidechain = sidechain
        self.connection = connection
        self.proline = proline
        self.imported = imported

    def __eq__(self, other):
        return self.kekule == other.kekule and self.backbone == other.backbone and self.sidechain == other.sidechain \
            and self.required == other.required and self.proline == other.proline and self.imported == other.imported

    @classmethod
    def from_mol(cls, mol, backbone, sidechain, imported=False):
        Chem.SanitizeMol(mol)
        Chem.Kekulize(mol)
        return cls(mol.ToBinary(), Chem.MolToSmiles(mol, kekuleSmiles=True), cls.is_required(mol),
                   backbone.to_reduced_dict(), sidechain.shared_id, sidechain.connection, cls.is_proline(mol), imported)

    @classmethod
    def from_dict(cls, data):
        mol = Chem.Mol(data['binary'])
        return cls(data['binary'], data['kekule'], cls.is_required(mol), data['backbone'], data['sidechain'],
                   data['connection'], cls.is_proline(mol), data['imported'], _id=data.get('_id', None), index=data['index'])

    @staticmethod
    def is_required(mol):
        return bool(AllChem.CalcNumAromaticRings(mol))

    @staticmethod
    def is_proline(mol):
        return bool(AllChem.CalcNumAliphaticRings(mol) and mol.HasSubstructMatch(PROLINE_N_TERM))

    @property
    def backbone_mol(self):
        return Chem.MolFromSmiles(self.backbone['kekule'])

    def to_dict(self):
        data = super().to_dict()
        data.pop('required')
        data.pop('proline')
        return data


class Peptide(AbstractMolecule):
    STRING = 'peptide'

    def __init__(self, binary, kekule, length, has_cap, monomers, _id=None):
        super().__init__(binary, kekule, _id)
        self.length = length
        self.has_cap = has_cap
        self.monomers = monomers

    def __eq__(self, other):
        return self.kekule == other.kekule and self.length == other.length and self.has_cap == other.has_cap and self.monomers == other.monomers

    @classmethod
    def from_mol(cls, mol, length, has_cap, monomers):
        Chem.SanitizeMol(mol)
        binary = mol.ToBinary()
        Chem.Kekulize(mol)
        monomers = [{'_id': monomer._id, 'sidechain': monomer.sidechain,
                     'proline': monomer.proline} for monomer in monomers]
        return cls(binary, Chem.MolToSmiles(mol, kekuleSmiles=True), length, has_cap, monomers)

    @classmethod
    def from_dict(cls, data):
        return cls(data['binary'], data['kekule'], data['length'], data['has_cap'], data['monomers'], _id=data.get('_id', None))


class TemplatePeptide(AbstractMolecule):
    STRING = 'template_peptide'

    def __init__(self, binary, kekule, template, peptide, length, _id=None):
        super().__init__(binary, kekule, _id)
        self.template = template
        self.peptide = peptide
        self.length = length

    def __eq__(self, other):
        return self.kekule == other.kekule and self.template == other.template and self.peptide == other.peptide

    @classmethod
    def from_mol(cls, mol, template, peptide):
        Chem.SanitizeMol(mol)
        binary = mol.ToBinary()
        Chem.Kekulize(mol)
        peptide = deepcopy(peptide.__dict__)
        peptide.pop('binary')
        return cls(binary, Chem.MolToSmiles(mol, kekuleSmiles=True), template._id, peptide, peptide.pop('length'))

    @classmethod
    def from_dict(cls, data):
        return cls(data['binary'], data['kekule'], data['template'], data['peptide'], data['length'], _id=data.get('_id', None))

    @property
    def monomers(self):
        return self.peptide['monomers']


class Macrocycle(AbstractMolecule):
    STRING = 'macrocycle'

    def __init__(self, binary, kekule, modifications, length, has_cap, template_peptide, template, reactions, _id=None):
        super().__init__(binary, kekule, _id)
        self.modifications = modifications
        self.length = length
        self.has_cap = has_cap
        self.template_peptide = template_peptide
        self.template = template
        self.reactions = reactions

    @classmethod
    def from_mol(cls, mol, modifications, template_peptide, reactions):
        mol = Chem.MolFromSmiles(Chem.MolToSmiles(mol))
        Chem.Kekulize(mol)
        cls.validate(mol)
        reactions = [rxn.to_reduced_dict() for rxn in reactions]
        return cls(mol.ToBinary(), Chem.MolToSmiles(mol, kekuleSmiles=True), modifications, template_peptide.length,
                   template_peptide.peptide['has_cap'], template_peptide._id, template_peptide.template, reactions)

    @classmethod
    def from_dict(cls, data):
        return cls(data['binary'], data['kekule'], data['modifications'], data['length'], data['has_cap'],
                   data['template_peptide'], data['template'], data['reactions'], _id=data.get('_id', None))

    @classmethod
    def add_modification(cls, original_macrocycle, new_macrocycle, modification):
        Chem.SanitizeMol(new_macrocycle)
        Chem.Kekulize(new_macrocycle)
        cls.validate(new_macrocycle)
        return cls(new_macrocycle.ToBinary(), Chem.MolToSmiles(new_macrocycle, kekuleSmiles=True),
                   original_macrocycle.modifications + modification, original_macrocycle.length, original_macrocycle.has_cap,
                   original_macrocycle.template_peptide, original_macrocycle.template, original_macrocycle.reactions)

    @staticmethod
    def validate(mol):
        if not [ring for ring in mol.GetRingInfo().BondRings() if len(ring) >= config.MIN_MACRO_RING_SIZE]:
            raise exceptions.InvalidMolecule(
                f'A macrocycle must have at least {config.MIN_MACRO_RING_SIZE} ring atoms!')

        return True


class Conformer(Macrocycle):
    STRING = 'conformer'

    def __init__(self, binary, kekule, modifications, length, has_cap, template_peptide, template, reactions, num_conformers, energies, rmsd, ring_rmsd, _id=None):
        super().__init__(binary, kekule, modifications, length, has_cap, template_peptide, template, reactions, _id)
        self.num_conformers = num_conformers
        self.energies = energies
        self.rmsd = rmsd
        self.ring_rmsd = ring_rmsd

    @classmethod
    def from_macrocycle(cls, conformer_mol, macrocycle, energies, rmsd, ring_rmsd):
        conformer_mol = Chem.RemoveHs(conformer_mol)
        Chem.SanitizeMol(conformer_mol)
        Chem.Kekulize(conformer_mol)
        cls.validate(conformer_mol, macrocycle)
        return cls(conformer_mol.ToBinary(), Chem.MolToSmiles(conformer_mol, kekuleSmiles=True), macrocycle.modifications,
                   macrocycle.length, macrocycle.has_cap, macrocycle.template_peptide, macrocycle.template, macrocycle.reactions,
                   conformer_mol.GetNumConformers(), energies, rmsd, ring_rmsd, _id=macrocycle._id)

    @classmethod
    def from_dict(cls, data):
        return cls(data['binary'], data['kekule'], data['modifications'], data['length'], data['has_cap'],
                   data['template_peptide'], data['template'], data['reactions'], data['num_conformers'], data['energies'], data['rmsd'], data['ring_rmsd'], _id=data.get('_id', None))

    @staticmethod
    def validate(mol, macrocycle):
        Macrocycle.validate(mol)

        if mol.GetNumConformers() <= 0:
            raise exceptions.InvalidMolecule('The conformer mol has no conformers')


class Reaction:
    STRING = 'reaction'

    def __init__(self, rxn_type, binary, smarts, template, reacting_mol, rxn_atom_idx, _id=None):
        self._id = _id
        self.type = rxn_type
        self.binary = binary
        self.smarts = smarts
        self.template = template
        self.reacting_mol = reacting_mol
        self.rxn_atom_idx = rxn_atom_idx

    def __eq__(self, other):
        return self.type == other.type and self.smarts == other.smarts and self.template == other.template \
            and self.reacting_mol == other.reacting_mol and self.rxn_atom_idx == other.rxn_atom_idx

    def __repr__(self):
        return print_model(self.STRING, self.__dict__)

    @classmethod
    def from_mols(cls, rxn_type, smarts, template, reacting_mol, rxn_atom_idx):

        if reacting_mol is not None:
            _id = reacting_mol.shared_id if isinstance(reacting_mol, Sidechain) else reacting_mol._id
            reacting_mol = {'_id': _id, 'kekule': reacting_mol.kekule}
        return cls(rxn_type, AllChem.ReactionFromSmarts(smarts).ToBinary(), smarts, template._id, reacting_mol, rxn_atom_idx)

    @classmethod
    def from_dict(cls, data):
        return cls(data['type'], data['binary'], data['smarts'], data['template'], data['reacting_mol'], data['rxn_atom_idx'], _id=data.get('_id', None))

    @property
    def rxn(self):
        return AllChem.ChemicalReaction(self.binary)

    def to_dict(self):
        data = deepcopy(self.__dict__)
        data.pop('_id')
        return data

    def to_reduced_dict(self):
        return {'_id': self._id, 'type': self.type}


class AbstractPrediction:
    def __init__(self, predictions, reacting_mol, solvent, _id):
        self._id = _id
        self.predictions = predictions
        self.reacting_mol = reacting_mol
        self.solvent = solvent

    def __eq__(self, other):
        return self.predictions == other.predictions and self.reacting_mol == other.reacting_mol and self.solvent == other.solvent

    def __repr__(self):
        print_model(self.STRING, self.__dict__)  # pylint: disable=no-member
        return ''

    def to_dict(self):
        data = deepcopy(self.__dict__)
        data.pop('_id')
        return data


class RegioSQMPrediction(AbstractPrediction):
    STRING = 'regiosqm'

    def __init__(self, predictions, reacting_mol, solvent, cutoff, _id=None):
        super().__init__(predictions, reacting_mol, solvent, _id)
        self.cutoff = cutoff

    def __eq__(self, other):
        return super().__eq__(other) and self.cutoff == other.cutoff

    @classmethod
    def from_dict(cls, data):
        return cls(data['predictions'], data['reacting_mol'], data['solvent'], data['cutoff'], _id=data.get('_id', None))


class pKaPrediction(AbstractPrediction):
    STRING = 'pka'

    def __init__(self, predictions, reacting_mol, solvent, _id=None):
        super().__init__(predictions, reacting_mol, solvent, _id)

    @classmethod
    def from_dict(cls, data):
        return cls(data['predictions'], data['reacting_mol'], data['solvent'], _id=data.get('_id', None))


class PeptidePlan:
    STRING = 'peptide_plan'

    PeptidePlanData = namedtuple('peptide_plan_data', 'reg_combos cap_combos length')

    def __init__(self, peptide_length):
        self.ids = None
        self.reg_combinations = set()
        self.cap_combinations = set()
        self.reg_length = peptide_length
        self.cap_length = peptide_length + 1

    def __iter__(self):
        self.combos = chain(self.reg_combinations, self.cap_combinations)
        return iter(self.combos)

    def __next__(self):
        return next(self.combos)

    def __len__(self):
        return len(self.reg_combinations) + len(self.cap_combinations)

    def __repr__(self):
        print('peptide length:', self.reg_length)
        print('combinations:\n')
        try:
            for _id, combination in self:
                print(_id, combination)
        except ValueError:
            for combination in self:
                print(combination)

        return ''

    @property
    def combinations(self):
        return self.reg_combinations.union(self.cap_combinations)

    def add(self, combination):
        if len(combination) == self.reg_length:
            self.reg_combinations.add(combination)
        elif len(combination) == self.cap_length:
            self.cap_combinations.add(combination)
        else:
            raise RuntimeError('The combination does not meet the peptide plan\'s requirements!')

    def data(self):
        for combo in self.combinations:
            yield {'combination': str(combo), 'length': self.reg_length}


get_all_model_strings = utils.get_module_strings(__name__)
