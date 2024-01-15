"""
OpenAI Assistants API - Function calling

Dec 2023, Timo Koehler
"""


class Functions:
    def getTimestampDelta(**args):
        deltaT = None
        t1 = args.get("current_timestamp")
        t2 = args.get("next_timestamp")
        if t1 is not None and t2 is not None:
            deltaT = t2 - t1
        return deltaT

    def getLogSeveritySubject(**args):
        return (args.get("severity"), args.get("subject"))

    def getSummary(**args):
        return args

    def getIpAddress(**args):
        return args


class Schemas:
    getTimestampDelta = {
        "name": "getTimestampDelta",
        "description": """Get the timestamp from the current and the next log record.
        Timestamps look like 1671420404.299, 1671420405.882.""",
        "parameters": {
            "type": "object",
            "properties": {
                "current_timestamp": {
                    "type": "number",
                    "description": """The timestamp is located in the second
                    column of the attached csv file.""",
                },
                "next_timestamp": {
                    "type": "number",
                    "description": """The timestamp is located in the second
                    column of the attached csv file.""",
                },
            },
            "required": ["current_timestamp", "next_timestamp"],
        },
    }

    getLogSeveritySubject = {
        "name": "getLogSeveritySubject",
        "description": """Get the message syslog severity level. Also get the component
        name which created the log message. The component name usually follows the
        timestamp or daytime information in the log message.""",
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "description": "The syslog logging severity.",
                },
                "subject": {
                    "type": "string",
                    "description": """The object or attribute representing a failure.""",
                },
            },
            "required": ["severity", "subject"],
        },
    }

    getSummary = {
        "name": "getSummary",
        "description": "Extract the main features from each log record.",
        "parameters": {
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "description": "The component which created the log.",
                },
                "failure": {
                    "type": "string",
                    "description": "The failure event in the message.",
                },
            },
            "required": [],
        },
    }

    getIpAddress = {
        "name": "getIpAddress",
        "description": """Extract the IP address from each log record.
        An IP address looks like 10.1.1.1, 192.168.192.155, 160.252.3.254.""",
        "parameters": {
            "type": "object",
            "properties": {
                "ip_address": {
                    "type": "string",
                    "description": "The IP address.",
                },
            },
        },
    }
