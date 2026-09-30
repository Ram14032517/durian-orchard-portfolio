import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('model',Path(__file__).resolve().parents[1]/'tools/train_monthly_production.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

class ModelTests(unittest.TestCase):
    def test_target_not_encoded(self):
        frame = pd.DataFrame({'province_code':['84'],'month':[7],'target_production_tonnes':[999]})
        x, columns = model.design(frame)
        self.assertEqual(x.shape,(1,60))
        self.assertEqual(x.sum(),1)
        self.assertNotIn('target_production_tonnes',columns)

    def test_constant_feature_is_safe(self):
        fit = model.fit_ridge(np.ones((4,2)),np.array([1.,2.,3.,4.]),10)
        np.testing.assert_allclose(model.predict(fit,np.ones((2,2))),[2.5,2.5])

    def test_mae_units(self):
        self.assertEqual(model.mae([0,20],[10,10]),10)

if __name__ == '__main__': unittest.main()
