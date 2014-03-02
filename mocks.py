"""
Mocks for running the server on a platform without naoqi
"""

import mock
import random

def get_data(name):
	if name == 'ALSentinel/BatteryLevel':
		return random.randint(1,5)

naoqi = mock.Mock(
	ALProxy=mock.Mock(
		return_value=mock.Mock(
			# behaviors
			getRunningBehaviors=mock.Mock(
				return_value=['foo', 'foo-channel/bar'],
			),
			getInstalledBehaviors=mock.Mock(
				return_value=[],
			),
			# audio
			getOutputVolume=mock.Mock(
				return_value=random.choice([10, 50, 88, 96]),
			),
			# memory
			getData=get_data,
		)))
