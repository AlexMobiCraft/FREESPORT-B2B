import os
from unittest.mock import MagicMock, call, patch

from django.test import TestCase

from apps.products.management.commands.import_products_from_1c import Command


class TestImportProductsFallback(TestCase):
    def test_import_variants_fallback_logic(self):
        """
        Verify that _import_variants_from_offers falls back to goods/import_files
        when offers/import_files does not exist.
        """
        command = Command()

        # Mock dependencies
        mock_parser = MagicMock()
        mock_processor = MagicMock()
        mock_parser.parse_offers_xml.return_value = (
            []
        )  # Return empty list so loop doesn't run, we just check base_dir logic

        data_dir = "/tmp/data"

        # Scenario 1: offers/import_files exists
        with patch("os.path.exists") as mock_exists:
            # First check: offers/import_files exists
            mock_exists.side_effect = (
                lambda result: True if result == os.path.join(data_dir, "offers", "import_files") else False
            )

            # Mock _collect_xml_files to return one file
            with patch.object(
                command,
                "_collect_xml_files",
                return_value=["/tmp/data/offers/offers.xml"],
            ):
                # Mock stdout
                command.stdout = MagicMock()

                command._import_variants_from_offers(data_dir, mock_parser, mock_processor, skip_images=False)

                # Verify no fallback message
                # The stdout.write calls are for step description (which we ignore) and fallback info
                # We check that the fallback info was NOT printed
                fallback_msg = "Изображения будут загружаться из"
                calls = [args[0] for args, _ in command.stdout.write.call_args_list]
                self.assertFalse(
                    any(fallback_msg in str(c) for c in calls),
                    "Fallback should not trigger when offers dir exists",
                )

        # Scenario 2: offers/import_files MISSING, goods/import_files EXISTS
        with patch("os.path.exists") as mock_exists:

            def side_effect(path):
                if path == os.path.join(data_dir, "offers", "import_files"):
                    return False  # offers dir missing
                if path == os.path.join(data_dir, "goods", "import_files"):
                    return True  # goods dir exists
                return True  # other paths exist

            mock_exists.side_effect = side_effect

            with patch.object(
                command,
                "_collect_xml_files",
                return_value=["/tmp/data/offers/offers.xml"],
            ):
                command.stdout = MagicMock()

                command._import_variants_from_offers(data_dir, mock_parser, mock_processor, skip_images=False)

                # Verify fallback message WAS printed
                fallback_msg = "Изображения будут загружаться из"
                calls = [args[0] for args, _ in command.stdout.write.call_args_list]
                self.assertTrue(
                    any(fallback_msg in str(c) for c in calls),
                    "Fallback SHOULD trigger when offers dir is missing and goods dir exists",
                )
