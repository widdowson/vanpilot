"""Tests for MCP tool definitions.

Verifies that all three MCP tools (display_bitmap, submit_bitmap,
get_screenshot) are correctly defined with proper schemas.
"""

import unittest

from mcp.src.tools import TOOL_DEFINITIONS, get_tool_by_name


class ToolDefinitionsTest(unittest.TestCase):
    """Tests that tool definitions are well-formed and complete."""

    def test_three_tools_defined(self):
        self.assertEqual(len(TOOL_DEFINITIONS), 3)

    def test_display_bitmap_definition(self):
        tool = get_tool_by_name("display_bitmap")
        self.assertIsNotNone(tool)
        self.assertEqual(tool["name"], "display_bitmap")
        self.assertIn("description", tool)
        schema = tool["inputSchema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("cache_key", schema["properties"])
        self.assertIn("blocking", schema["properties"])
        self.assertIn("cache_key", schema["required"])

    def test_submit_bitmap_definition(self):
        tool = get_tool_by_name("submit_bitmap")
        self.assertIsNotNone(tool)
        self.assertEqual(tool["name"], "submit_bitmap")
        self.assertIn("description", tool)
        schema = tool["inputSchema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("image_data", schema["properties"])
        self.assertIn("image_data", schema["required"])

    def test_get_screenshot_definition(self):
        tool = get_tool_by_name("get_screenshot")
        self.assertIsNotNone(tool)
        self.assertEqual(tool["name"], "get_screenshot")
        self.assertIn("description", tool)
        schema = tool["inputSchema"]
        self.assertEqual(schema["type"], "object")

    def test_all_tools_have_descriptions(self):
        for tool in TOOL_DEFINITIONS:
            with self.subTest(tool=tool["name"]):
                self.assertTrue(
                    len(tool["description"]) > 0,
                    f"Tool {tool['name']} has empty description",
                )

    def test_get_tool_by_name_returns_none_for_unknown(self):
        self.assertIsNone(get_tool_by_name("nonexistent_tool"))

    def test_display_bitmap_blocking_defaults_false(self):
        tool = get_tool_by_name("display_bitmap")
        blocking_prop = tool["inputSchema"]["properties"]["blocking"]
        self.assertEqual(blocking_prop.get("default"), False)


if __name__ == "__main__":
    unittest.main()
