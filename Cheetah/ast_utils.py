from __future__ import absolute_import
from __future__ import unicode_literals

import ast

import six


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
            if six.PY2:  # pragma: no cover (PY2)
                self.visit(node.name)
            else:  # pragma: no cover (PY3)
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

    if six.PY2:  # pragma: no cover (PY2)
        visit_With = visit_withitem

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
