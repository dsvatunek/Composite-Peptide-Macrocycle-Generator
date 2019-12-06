class MissingMapNumber(Exception):
    """
    Raised when Mol is missing atom map numbers in SMILES string.
    """


class MergeError(Exception):
    """
    Raised when merging of two molecules fails.
    """


class InvalidMolecule(Exception):
    """
    Raised when an operation on a molecule cannot be performed due to the molecule missing a feature required for that
    operation.
    """
