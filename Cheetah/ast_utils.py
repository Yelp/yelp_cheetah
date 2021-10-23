import ast
import collections


def _to_top_level_name(name):
    # We only really care about the first segment for name resolution
    return (name.asname or name.name).partition('.')[0]


def get_imported_names(import_statement):
    ast_import = ast.parse(import_statement).body[0]
    return [
        _to_top_level_name(name)
        for name in ast_import.names
        if _to_top_level_name(name) != '*'
    ]


class TargetsVisitor(ast.NodeVisitor):
    def __init__(self):
        self.lvalues = []

    def visit_Name(self, node):
        self.lvalues.append(node.id)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.lvalues.append(node.name)

    def visit_ClassDef(self, node):
        self.lvalues.append(node.name)

    def visit_FunctionDef(self, node):
        self.lvalues.append(node.name)


class TopLevelVisitor(ast.NodeVisitor):
    def __init__(self):
        self.targets_visitor = TargetsVisitor()

    def visit_Assign(self, node):
        for target in node.targets:
            self.targets_visitor.visit(target)

    def visit_withitem(self, node):
        if node.optional_vars:
            self.targets_visitor.visit(node.optional_vars)

    def visit_For(self, node):
        self.targets_visitor.visit(node.target)

    def _target_visit(self, node):
        self.targets_visitor.visit(node)

    visit_ExceptHandler = visit_ClassDef = visit_FunctionDef = _target_visit


def get_lvalues(expression):
    ast_obj = ast.parse(expression)
    visitor = TopLevelVisitor()
    visitor.visit(ast_obj)
    return visitor.targets_visitor.lvalues


def get_argument_names(argspec):
    ast_obj = ast.parse(f'def _({argspec}): pass').body[0].args
    names = [name.arg for name in ast_obj.args]
    if ast_obj.vararg:
        names.append(ast_obj.vararg.arg)
    if ast_obj.kwarg:
        names.append(ast_obj.kwarg.arg)
    if ast_obj.kwonlyargs:
        names.extend(arg.arg for arg in ast_obj.kwonlyargs)
    # Raise a nice message on duplicate arguments (since ast doesn't)
    counter = collections.Counter(names)
    duplicate_arguments = sorted(
        name for name, count in counter.items() if count > 1
    )
    if duplicate_arguments:
        raise SyntaxError(
            'Duplicate arguments: {}'.format(', '.join(duplicate_arguments)),
        )
    return set(names)
