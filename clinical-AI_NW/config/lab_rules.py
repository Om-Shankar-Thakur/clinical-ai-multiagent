LAB_RULES = {
   "platelets": {
       "low": {
           "threshold": 100000,
           "signal": "low platelets",
           "critical": True
       }
   },
   "hematocrit": {
       "high": {
           "threshold": 50,
           "signal": "elevated hematocrit",
           "critical": False
       }
   },
   "sodium": {
       "high": {
           "threshold": 145,
           "signal": "high sodium",
           "critical": False
       }
   },
   "hemoglobin": {
       "low": {
           "threshold": 10,
           "signal": "low hemoglobin",
           "critical": False
       }
   },
   "oxygen": {
       "low": {
           "threshold": 92,
           "signal": "low oxygen saturation",
           "critical": True
       }
   },
   "glucose": {
       "high": {
           "threshold": 200,
           "signal": "high blood sugar",
           "critical": True
       }
   }
}