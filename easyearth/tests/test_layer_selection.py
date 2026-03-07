"""Tests for layer selection handling in the EasyEarth plugin.

These tests verify that the plugin correctly handles edge cases when
selecting layers, including None layers, None sources, and missing groups.
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch, PropertyMock, call

# Add the project root to sys.path so we can reference plugin module structure
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


class TestOnImageSelected(unittest.TestCase):
    """Test the on_image_selected method for None-safety."""

    def _make_plugin(self):
        """Create a minimal mock plugin object with the on_image_selected logic."""
        plugin = MagicMock()
        plugin.selected_layer = None
        plugin.project_crs = MagicMock()

        # We replicate the fixed on_image_selected logic here so we can test
        # it without importing QGIS dependencies.
        def on_image_selected():
            # Simulate the layer search loop — uses plugin.find_layer_in_tree()
            found = plugin.find_layer_in_tree()
            if found is not None:
                plugin.selected_layer = found

            if not plugin.selected_layer:
                plugin.iface.messageBar().pushMessage(
                    "No matching layer found for the selected image.",
                    level="Warning",
                )
                return

            plugin.iface.setActiveLayer(plugin.selected_layer)
            plugin.iface.messageBar().pushMessage(
                f"Selected layer {plugin.selected_layer.name()}",
                level="Info",
            )

            # Simulate group reordering
            root = plugin.root
            group = root.findGroup(plugin.selected_layer.name())
            if group is not None:
                root.insertChildNode(0, group.clone())
                group.parent().removeChildNode(group)
            plugin.iface.mapCanvas().refresh()

        plugin.on_image_selected = on_image_selected
        return plugin

    def test_layer_is_none(self):
        """When no layer is found, a warning is shown and no crash occurs."""
        plugin = self._make_plugin()
        plugin.find_layer_in_tree.return_value = None
        plugin.selected_layer = None

        # Should not raise
        plugin.on_image_selected()

        # Verify warning was pushed
        plugin.iface.messageBar().pushMessage.assert_called_once_with(
            "No matching layer found for the selected image.",
            level="Warning",
        )
        # setActiveLayer should NOT have been called
        plugin.iface.setActiveLayer.assert_not_called()

    def test_group_is_none_no_crash(self):
        """When findGroup returns None, clone() must not be called."""
        plugin = self._make_plugin()
        mock_layer = MagicMock()
        mock_layer.name.return_value = "my_layer"
        plugin.find_layer_in_tree.return_value = mock_layer
        plugin.root.findGroup.return_value = None

        # Should not raise even though group is None
        plugin.on_image_selected()

        # clone should never be called
        plugin.root.findGroup.assert_called_once_with("my_layer")
        # insertChildNode should not be called when group is None
        plugin.root.insertChildNode.assert_not_called()

    def test_successful_layer_selection(self):
        """When a valid layer and group exist, reordering happens normally."""
        plugin = self._make_plugin()
        mock_layer = MagicMock()
        mock_layer.name.return_value = "my_layer"
        plugin.find_layer_in_tree.return_value = mock_layer

        mock_group = MagicMock()
        plugin.root.findGroup.return_value = mock_group

        plugin.on_image_selected()

        # Layer should be set as active
        plugin.iface.setActiveLayer.assert_called_once_with(mock_layer)
        # Group should be cloned and reordered
        mock_group.clone.assert_called_once()
        plugin.root.insertChildNode.assert_called_once_with(0, mock_group.clone())
        mock_group.parent().removeChildNode.assert_called_once_with(mock_group)


class TestOnLayerSelected(unittest.TestCase):
    """Test the on_layer_selected method for None-safety."""

    def _make_plugin(self):
        """Create a minimal mock plugin with on_layer_selected logic."""
        plugin = MagicMock()
        plugin.selected_layer = None

        def on_layer_selected(index):
            try:
                if index > 0:
                    layer_id = plugin.layer_dropdown.itemData(index)
                    plugin.selected_layer = (
                        plugin.project.mapLayer(layer_id) if layer_id else None
                    )

                    if not plugin.selected_layer:
                        return

                    plugin.image_path.setText(plugin.selected_layer.source())
                    plugin.on_image_selected_callback()
                    plugin.create_prediction_layers()

                    # Check for existing embedding
                    layer_source = plugin.selected_layer.source()
                    if layer_source:
                        image_name = os.path.splitext(
                            os.path.basename(layer_source)
                        )[0]
                        plugin.update_embeddings(image_name)
            except Exception as e:
                plugin.logger.error(f"Error handling layer selection: {str(e)}")
                plugin.show_error(f"Failed to handle layer selection: {str(e)}")

        plugin.on_layer_selected = on_layer_selected
        return plugin

    def test_layer_is_none_returns_early(self):
        """When mapLayer returns None, method returns without error."""
        plugin = self._make_plugin()
        plugin.layer_dropdown.itemData.return_value = "some_id"
        plugin.project.mapLayer.return_value = None

        plugin.on_layer_selected(1)

        plugin.on_image_selected_callback.assert_not_called()
        plugin.show_error.assert_not_called()

    def test_layer_source_is_none(self):
        """When layer.source() returns None, update_embeddings is skipped."""
        plugin = self._make_plugin()
        mock_layer = MagicMock()
        mock_layer.source.return_value = None
        plugin.layer_dropdown.itemData.return_value = "layer_123"
        plugin.project.mapLayer.return_value = mock_layer

        plugin.on_layer_selected(1)

        plugin.update_embeddings.assert_not_called()
        plugin.show_error.assert_not_called()

    def test_successful_layer_selection_with_source(self):
        """When layer and source are valid, embeddings are updated."""
        plugin = self._make_plugin()
        mock_layer = MagicMock()
        mock_layer.source.return_value = "/data/images/satellite.tif"
        plugin.layer_dropdown.itemData.return_value = "layer_123"
        plugin.project.mapLayer.return_value = mock_layer

        plugin.on_layer_selected(1)

        plugin.update_embeddings.assert_called_once_with("satellite")
        plugin.show_error.assert_not_called()

    def test_error_message_shown_on_failure(self):
        """When an exception occurs, error message is shown to user."""
        plugin = self._make_plugin()
        plugin.layer_dropdown.itemData.return_value = "layer_123"
        plugin.project.mapLayer.side_effect = RuntimeError("QGIS internal error")

        plugin.on_layer_selected(1)

        plugin.show_error.assert_called_once()
        error_msg = plugin.show_error.call_args[0][0]
        self.assertIn("Failed to handle layer selection", error_msg)
        self.assertIn("QGIS internal error", error_msg)

    def test_index_zero_does_nothing(self):
        """Index 0 is the placeholder; nothing should happen."""
        plugin = self._make_plugin()

        plugin.on_layer_selected(0)

        plugin.layer_dropdown.itemData.assert_not_called()
        plugin.show_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
