from argparse import ArgumentParser
import cpmg.parallelizers as p
import cpmg.orchestrator as o


def execute(command_line_args):
    params = o.ExecutionParameters(vars(command_line_args))
    orchestrator = o.Orchestractor.from_execution_parameters(params)
    return orchestrator.execute(**params.operation_parameters)


class GenerateArgParser:
    def __init__(self):
        parser = ArgumentParser()
        subparsers = parser.add_subparsers(dest='operation')
        parser.add_argument('-p', '--parallelism', choices=p.get_all_parallelizer_strings(), nargs='?',
                            const=p.SingleProcess.STRING, default=p.SingleProcess.STRING,
                            help='Selects which level of parallelism to execute the molecule generation with')

        parent_parser = ArgumentParser(add_help=False)
        parent_parser.add_argument('-l', '--length', '--peptide_length', type=int, choices=[3, 4, 5],
                                         required=True, dest='peptide_length',
                                         help='The number of monomers to assemble into a peptide.')

        sidechain_parser = subparsers.add_parser('sidechain')
        sidechain_parser.set_defaults(func=execute)

        monomer_parser = subparsers.add_parser('monomer')
        monomer_parser.set_defaults(func=execute)

        inter_reaction_parser = subparsers.add_parser('inter_reaction')
        inter_reaction_parser.set_defaults(func=execute)

        intra_reaction_parser = subparsers.add_parser('intra_reaction')
        intra_reaction_parser.set_defaults(func=execute)

        peptide_plan_parser = subparsers.add_parser('peptide_plan', parents=[parent_parser])
        peptide_plan_parser.add_argument('-n', '--num', '--num_peptides', type=int, required=True, dest='num_peptides',
                                         help='The number of peptides to generate.')
        peptide_plan_parser.set_defaults(func=execute)

        peptide_parser = subparsers.add_parser('peptide', parents=[parent_parser])
        peptide_parser.set_defaults(func=execute)

        template_peptide_parser = subparsers.add_parser('template_peptide', parents=[parent_parser])
        template_peptide_parser.set_defaults(func=execute)

        args = parser.parse_args()
        self.return_val = args.func(args)


if __name__ == "__main__":
    generate_parser = GenerateArgParser()
