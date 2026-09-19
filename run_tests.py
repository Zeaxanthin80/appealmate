"""Direct test runner.

unittest's automatic discovery misbehaves in this layout on Windows, so the
suite is built explicitly — but from *every* TestCase class in the module, found
by introspection. An earlier version listed the classes by hand, which silently
skipped any class added later; that is exactly the failure mode this avoids.
"""
import inspect
import sys
import unittest

sys.path.insert(0, ".")
import test_appealmate  # noqa: E402

loader = unittest.TestLoader()
suite = unittest.TestSuite()

classes = [
    obj for _name, obj in inspect.getmembers(test_appealmate, inspect.isclass)
    if issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase
]
classes.sort(key=lambda c: c.__name__)

print("Test classes discovered: %s\n" % ", ".join(c.__name__ for c in classes))
for cls in classes:
    suite.addTests(loader.loadTestsFromTestCase(cls))

result = unittest.TextTestRunner(verbosity=2).run(suite)
print("\nRan %d tests, %d failure(s), %d error(s)"
      % (result.testsRun, len(result.failures), len(result.errors)))
sys.exit(0 if result.wasSuccessful() else 1)
