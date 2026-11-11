"""Validação de SQL gerado pelo modelo."""

from pergunteoee.sql.validator import SqlValidationError, validate_sql

__all__ = ["SqlValidationError", "validate_sql"]
