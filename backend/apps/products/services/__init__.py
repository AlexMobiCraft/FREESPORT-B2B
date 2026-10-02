"""
Services для работы с импортом данных из 1С
"""

from .parser import XMLDataParser
from .variant_import import VariantImportProcessor

__all__ = ["XMLDataParser", "VariantImportProcessor"]
