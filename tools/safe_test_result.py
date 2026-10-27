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
        self.started=time.monotonic()

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
        # unittest reports setUpClass/tearDownClass errors as _ErrorHolder,
        # without a test method. Reserve 10000 for fixture failures so a setup
        # error cannot crash the reporter or disappear from harness evidence.
        method=getattr(test,"_testMethodName",None)
        number=int(method.split("_")[1]) if method else 10000
        diagnostic={"test_number":number,
                                 "kind":kind,"category":category,
                                 "elapsed_ms":round((time.monotonic()-self.started)*1000)}
        phase=getattr(err[1],"ocp_phase",None);limit=getattr(err[1],"ocp_timeout_seconds",None)
        if (category=="subprocess_timeout" and phase in ("site_engine_startup","site_example_execution","app_engine_startup","app_example_execution")
                and type(limit) in (int,float) and 0<limit<=3600):
            diagnostic.update(phase=phase,timeout_seconds=limit)
        self.diagnostics.append(diagnostic)

    def addFailure(self, test, err):
        self.record(test,err,"failure")
        super().addFailure(test,err)

    def addError(self, test, err):
        self.record(test,err,"error")
        super().addError(test,err)
