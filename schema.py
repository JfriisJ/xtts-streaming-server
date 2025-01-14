# schema.py

JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "Title": {
            "type": "string",
            "description": "The title of the document."
        },
        "Sections": {
            "type": "array",
            "description": "An array of sections in the document.",
            "items": {
                "type": "object",
                "properties": {
                    "Heading": {
                        "type": "string",
                        "description": "The heading of the section."
                    },
                    "Content": {
                        "oneOf": [
                            {
                                "type": "string",
                                "description": "The content of the section as a string."
                            },
                            {
                                "type": "array",
                                "description": "The content of the section as an array of strings.",
                                "items": {
                                    "type": "string"
                                }
                            }
                        ]
                    },
                    "Subsections": {
                        "type": "array",
                        "description": "An array of subsections within the section.",
                        "items": {
                            "$ref": "#/definitions/section"
                        }
                    }
                },
                "required": ["Heading"],
                "additionalProperties": False
            }
        }
    },
    "required": ["Title", "Sections"],
    "additionalProperties": False,
    "definitions": {
        "section": {
            "type": "object",
            "properties": {
                "Heading": {
                    "type": "string",
                    "description": "The heading of the subsection."
                },
                "Content": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "The content of the subsection as a string."
                        },
                        {
                            "type": "array",
                            "description": "The content of the subsection as an array of strings.",
                            "items": {
                                "type": "string"
                            }
                        }
                    ]
                },
                "Subsections": {
                    "type": "array",
                    "description": "An array of nested subsections.",
                    "items": {
                        "$ref": "#/definitions/section"
                    }
                }
            },
            "required": ["Heading"],
            "additionalProperties": False
        }
    }
}
