"""Bounded, credential-free unittest diagnostics shared by installed consumers."""
import json
import subprocess
import time
import unittest
from conformance.core_contract import ContractError


class DiagnosticResult(unittest.TextTestResult):
    """Record bounded failure metadata; never retain tracebacks, inputs or messages."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostics=[]

    def startTest(self, test):
        self.started=time.monotonic()
        super().startTest(test)

    def record(self, test, err, kind):
        category="exception"
        for cls,label in ((subprocess.TimeoutExpired,"subprocess_timeout"),
                          (json.JSONDecodeError,"invalid_json"),(ContractError,"contract"),
                          (AssertionError,"assertion")):
            if issubclass(err[0],cls):
                category=label;break
        self.diagnostics.append({"test_number":int(test._testMethodName.split("_")[1]),
                                 "kind":kind,"category":category,
                                 "elapsed_ms":round((time.monotonic()-self.started)*1000)})

    def addFailure(self, test, err):
        self.record(test,err,"failure")
        super().addFailure(test,err)

    def addError(self, test, err):
        self.record(test,err,"error")
        super().addError(test,err)
