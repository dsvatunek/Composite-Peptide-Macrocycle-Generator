from abc import ABC, abstractmethod
from collections import namedtuple

import macrocycles.iterators as iterators
import macrocycles.molecules as molecules
import macrocycles.project_io as project_io
import macrocycles.reactions as reactions


class IDataHandler(ABC):
    """
    Interface for classes that couple together specific IO classes in order to supply and write data for a specific
    Generator class.
    """

    @abstractmethod
    def load(self):
        """
        Abstract method for calling load() on each IO class of the specific derived DataHandler and returning the data
        together.
        """

    @abstractmethod
    def save(self, data):
        """
        Abstract method for calling save() on the IO class used for saving data generated by the Generator.
        """


class SCCMDataHandler(IDataHandler):
    """
    Implementation of a IDataHandler used to supply and write the data needed and generated by the
    SideChainConnectionModifier class.
    """

    def __init__(self, **kwargs):
        """
        Initializer method that creates instances of SideChainIO and IDIterator and assigns them to instance variables.
        """

        self.sidechain_io = project_io.get_sidechain_io()
        self.id_iterator = iterators.IDIterator(project_io.get_id_io())

    def load(self):
        """
        Method that calls the SideChainIO's load() method and returns the loaded data.

        Returns:
            iterable[dict]: An iterable of sidechain documents.
        """

        return self.sidechain_io.load()

    def save(self, data):
        """
        Method that calls the SideChainIO's save() method with the provided data as well as the IDIterator's save()
        method.

        Args:
            data (iterable[dict]): An iterable of new sidechain documents generated by the SideChainConnectionModifier.
        """

        self.sidechain_io.save(data)
        self.id_iterator.save()


class MGDataHandler(IDataHandler):
    """
    Implementation of IDataHandler used to supply and write the data needed and generated by the MonomerGenerator class.
    """

    def __init__(self, **kwargs):
        """
        Initializer method that creates instances of SideChainIO, MonomerIO, and IndexIterator and assigns them to
        instance variables.
        """

        self.sidechain_loader = project_io.get_sidechain_io()
        self.monomer_saver = project_io.get_monomer_io()
        self.index_iterator = iterators.IndexIterator(project_io.get_index_io())

    def load(self):
        """
        Method that calls the SideChainIO's load() method and returns the loaded data.

        Returns:
            iterable[dict]: An iterable of sidechain documents.
        """

        return self.sidechain_loader.load()

    def save(self, data):
        """
        Method that calls the MonomerIO's save() method with the provided data as well as the IndexIterator's save()
        method.

        Args:
            data (iterable[dict]): An iterable of new monomer documents generated by the MonomerGenerator.
        """

        self.monomer_saver.save(data)
        self.index_iterator.save()


class PGDataHandler(IDataHandler):
    """
    Implementation of IDataHandler used to supply and write the data needed and generated by the PeptideGenerator class.
    """

    def __init__(self, **kwargs):
        """
        Initializer method that creates instances of PeptideIO, and PeptidePlannerIO and assigns them to instance
        variables.

        Args:
            peptide_length (int): A keyword argument that specifies the length of peptide that is being generated.
        """

        self.peptide_saver = project_io.get_peptide_io(**kwargs)
        self.plan_loader = project_io.PeptidePlannerIO(kwargs['peptide_length'])

    def load(self):
        """
        Method that calls the PeptidePlannerIO's load() method and returns the loaded data.

        Returns:
            iterable[dict]: An iterable of monomer indexes.
        """

        return self.plan_loader.load()

    def save(self, data):
        """
        Method that calls the PeptideIO's save() method with the provided data.

        Args:
            data (iterable[dict]): An iterable of new peptide documents generated by the PeptideGenerator.
        """

        self.peptide_saver.save(data)


class TPGDataHandler(IDataHandler):
    """
    Implementation of IDataHandler used to supply and write the data needed and generated by the
    TemplatePeptideGenerator class.
    """

    def __init__(self, **kwargs):
        """
        Initializer method that creates instances of PeptideIO, and TemplatePeptideIO and assigns them to instance
        variables.

        Args:
            peptide_length (int): A keyword argument that specifies the length of peptide that is to be used to generate
                template_peptides. This keyword argument is only necessary when DATA_FORMAT is json.
        """

        self.peptide_loader = project_io.get_peptide_io(**kwargs)
        self.template_peptide_saver = project_io.get_template_peptide_io(**kwargs)

    def load(self):
        """
        Method that calls the PeptideIO's load() method and returns the loaded data.

        Returns:
            iterable[dict]: An iterable of peptide documents.
        """

        return self.peptide_loader.load()

    def save(self, data):
        """
        Method that calls the TemplatePeptideIO's save() method with the provided data.

        Args:
            data (iterable[dict]): An iterable of new template_peptide documents generated by the
                TemplatePeptideGenerator.
        """

        self.template_peptide_saver.save(data)


class MCGDataHandler(IDataHandler):
    """
    Implementation of IDataHandler used to supply and write the data needed and generated by the MacrocycleGenerator
    class.
    """

    def __init__(self, **kwargs):
        """
        Initializer method that creates instances of TemplatePeptideIO, ReactionIO, and MacrocycleIO and assigns them to
        instance variables.

        Args:
            peptide_length (int): A keyword argument that specifies the length of peptide that is in the
                template_peptides that are to be used to generate macrocycles. This keyword argument is only necessary
                when DATA_FORMAT is json.
            start (int): A keyword argument that specifies the start index of a chunk of template_peptide data to
                return. This keyword argument is only necessary when DATA_FORMAT is json.
            end (int): A keyword argument that specifies the end index of a chunk of template_peptide data to
                return. This keyword argument is only necessary when DATA_FORMAT is json.
        """

        self.template_peptide_loader = project_io.get_template_peptide_io(**kwargs)
        self.reaction_loader = project_io.get_reaction_io()
        self.macrocycle_saver = project_io.get_macrocycle_io(**kwargs)

        try:
            self.start = kwargs['start']
            self.end = kwargs['end']
        except KeyError:
            self.start = -1
            self.end = 1000000000

    def load(self):
        """
        Method that calls the TemplatePeptideIO and ReactionIO's load() method and returns the loaded data as tuple.

        Returns:
            tuple[iterable[dict]]: A tuple of iterables, where the first index contains the template_peptide documents
                and the second index contains the reaction documents.
        """

        MacrocycleGeneratorData = namedtuple('MacrocycleGeneratorData', 'template_peptides reactions')
        return MacrocycleGeneratorData(self.load_template_peptides(), self.reaction_loader.load())

    def save(self, data):
        """
        Method that calls the MacrocycleIO's save() method with the provided data.

        Args:
            data (iterable[dict]): An iterable of new macrocycle documents generated by the MacrocycleGenerator.
        """

        self.macrocycle_saver.save(data)

    def load_template_peptides(self):
        """
        Helper method for using the instance variables self.start and self.end, to load the specified chunk of
        template_peptide molecules.

        Yields:
            dict: A template_peptide document.
        """

        for i, template_peptide in enumerate(self.template_peptide_loader.load()):
            if i < self.start:
                continue
            elif i >= self.end:
                break
            else:
                yield template_peptide


class ConformerGeneratorDataHandler(IDataHandler):

    def __init__(self, **kwargs):

        self.macrocycle_loader = project_io.get_macrocycle_io(**kwargs)
        # self.conformer_saver = project_io.get_conformer_io(**kwargs)

    def load(self):
        return self.macrocycle_loader.load()

    def save(self, data):
        # pass
        self.macrocycle_loader.update(data)


class UMRGDataHandler(IDataHandler):
    """
    Implementation of IDataHandler used to supply and write the data needed and generated by the
    UniMolecularReactionGenerator class.
    """

    def __init__(self, **kwargs):
        """
        Initializer method that creates instances of ReactionIO and assigns it to instance variable.
        """

        self.reaction_saver = project_io.get_reaction_io()

    def load(self):
        """
        Method that calls molecules.get_templates(), reactions.get_unimolecular_reactions() and returns the data.

        Returns:
            tuple[iterable]: A tuple containing template molecules and unimolecular reactions.
        """

        return molecules.get_templates(), reactions.get_unimolecular_reactions()

    def save(self, data):
        """
        Method that calls the ReactionIO's save() method with the provided data.

        Args:
            data (iterable[dict]): An iterable of new unimolecular reaction documents generated by the
                UniMolecularReactionGenerator.
        """

        self.reaction_saver.save(data)


class BMRGDataHandler(IDataHandler):
    """
    Implementation of IDataHandler used to supply and write the data needed and generated by the
    BiMolecularReactionGenerator class.
    """

    def __init__(self, **kwargs):
        """
        Initializer method that creates instances of SideChainIO, MonomerIO, and ReactionIO and assigns them to instance
        variables.
        """

        self.sidechain_loader = project_io.get_sidechain_io()
        self.monomer_loader = project_io.get_monomer_io()
        self.reaction_saver = project_io.get_reaction_io()

    def load(self):
        """
        Method that calls load() on both the SideChainIO and MonomerIO, filtering out sidechains that dont have a methyl
        connection, and monomers that are not required or not imported. The combined results are then returned as a
        tuple with the bimolecular reactions returned by reactions.get_bimolecular_reactions().

        Returns:
            tuple[iterable]: A tuple containing sidechain and monomer molecules and bimolecular reactions.
        """

        reacting_mols = list(filter(lambda x: x['connection'] == 'methyl', self.sidechain_loader.load()))
        reacting_mols.extend(list(filter(lambda x: x['required'] and x['imported'], self.monomer_loader.load())))
        return reacting_mols, reactions.get_bimolecular_reactions()

    def save(self, data):
        """
        Method that calls the ReactionIO's save() method with the provided data.

        Args:
            data (iterable[dict]): An iterable of new bimolecular reaction documents generated by the
                BiMolecularReactionGenerator.
        """

        self.reaction_saver.save(data)
