import typing as typ
from collections import namedtuple
from manager.master.build import Build
from pyparsing import Word, alphas, Char

###############################################################################
#                                 Macro Tokens                                #
###############################################################################
L_ENCLOSER = "<"
R_ENCLOSER = ">"
MACRO_VER = L_ENCLOSER + "version" + R_ENCLOSER
MACRO_DATETIEM = L_ENCLOSER + "datetime" + R_ENCLOSER
MACRO_EXTRA = L_ENCLOSER + "extra" + R_ENCLOSER
MACRO_OP_EXIST = "?"

def macros_trans(build: Build, specs: typ.Dict[str, str]) -> None:
    """
    Replace macros within commands of the Build.
    """
    commands = build.getCmd()
    output = build.getOutput()

    # Create Macro Parser
    operator = Char(MACRO_OP_EXIST)  # type: ignore
    macro_parser = L_ENCLOSER + Word(alphas) + R_ENCLOSER  # type: ignore
    macro_parser_with_op = \
        L_ENCLOSER + Word(alphas) + operator + Word(alphas) + R_ENCLOSER  # type: ignore

    parser = macro_parser ^ macro_parser_with_op  # type: ignore

    # Do Transformation
    parser.setParseAction(  # type: ignore
        lambda s, loc, tokens: macros_do_trans(tokens, specs)
    )

    build.setCmd(
        [parser.transformString(cmd) for cmd in commands]  # type: ignore
    )
    build.setOutput([parser.transformString(output)])  # type: ignore


###############################################################################
#                             Macro Trans Function                            #
###############################################################################
def macros_do_trans(macro: typ.List[str], specs: typ.Dict[str, str]) -> str:
    macro_str = "".join(macro)

    # Macro with operator
    if MACRO_OP_EXIST in macro_str:
        return macro_do_exist_op(macro_str, specs)

    if macro_str not in specs:
        return ""

    return specs[macro_str]


def macro_do_exist_op(macro: str, specs: typ.Dict[str, str]) -> str:
    macro_no_encloser = macro[1:-1]
    l, r = macro_no_encloser.split(MACRO_OP_EXIST)
    if l in specs:
        return specs[with_encloser(l)]
    else:
        return specs[with_encloser(r)]


###############################################################################
#                                     Misc                                    #
###############################################################################
def with_encloser(macro: str) -> str:
    return L_ENCLOSER + macro + R_ENCLOSER
