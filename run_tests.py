"""Direct test runner — avoids unittest's module-name discovery quirks."""
import sys
import unittest

sys.path.insert(0, ".")
import test_appealmate  # noqa: E402

loader = unittest.TestLoader()
suite = unittest.TestSuite()
for cls in (test_appealmate.TestScenarioMatching,
            test_appealmate.TestFullConversation,
            test_appealmate.TestRefusalPath,
            test_appealmate.TestVoice):
    suite.addTests(loader.loadTestsFromTestCase(cls))
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
