#from __future__ import print_function
import os
import json

import cherrypy
try:
	import naoqi
except ImportError:
	# mock the naoqi module so we can test this on a platform without naoqi
	import mock
	naoqi = mock.Mock(
		ALProxy=mock.Mock(
			return_value=mock.Mock(
				getRunningBehaviors=mock.Mock(
					return_value=[],
				),
				getInstalledBehaviors=mock.Mock(
					return_value=[],
				),
			)))

class BaseHandler(object):
	exposed = True

def load_al_module(name):
	cherrypy.serving.request.module = naoqi.ALProxy(name, 'localhost', 9559)
cherrypy.tools.al_module_loader = cherrypy.Tool('before_handler', load_al_module)

class Behavior(BaseHandler):
	def GET(self):
		req = cherrypy.request
		name = req.behavior_name
		if not name in req.module.getInstalledBehaviors():
			raise cherrypy.NotFound()
		return name

	def PUT(self):
		"Install a new behavior"
		behavior_crg = cherrypy.request.body
		raise NotImplementedError()

class InstalledBehaviors(BaseHandler):
	def GET(self):
		req = cherrypy.request
		resp = cherrypy.response
		resp.headers['Content-Type'] = 'application/json'
		return json.dumps(req.module.getInstalledBehaviors())

class RunningBehaviors(BaseHandler):
	def GET(self):
		req = cherrypy.request
		resp = cherrypy.response
		resp.headers['Content-Type'] = 'application/json'
		return json.dumps(req.module.getRunningBehaviors())

	def POST(self):
		req = cherrypy.request
		name = req.body.read()
		req.module.post.runBehavior(name)

	def DELETE(self, name):
		req = cherrypy.request
		req.module.stopBehavior(name)

class Behaviors(BaseHandler):
	_cp_config = {
		'tools.al_module_loader.on': True,
		'tools.al_module_loader.name': 'ALBehaviorManager',
	}
	installed = InstalledBehaviors()
	running = RunningBehaviors()

	def GET(self):
		req = cherrypy.request
		req.headers['Content-Type'] = 'application/json'
		return json.dumps(req.module.getInstalledBehaviors())

	def _cp_dispatch(self, vpath):
		cherrypy.serving.request.behavior_name = vpath.pop(0)
		return Behavior()

class AudioVolume(BaseHandler):
	def GET(self):
		req = cherrypy.request
		req.headers['Content-Type'] = 'application/json'
		return json.dumps(req.module.getOutputVolume())

	def PUT(self):
		req = cherrypy.request
		req.module.setOutputVolume(int(req.body.read()))

class AudioDevice(BaseHandler):
	_cp_config = {
		'tools.al_module_loader.on': True,
		'tools.al_module_loader.name': 'ALAudioDevice',
	}

	volume = AudioVolume()

class TextToSpeech(BaseHandler):
	_cp_config = {
		'tools.al_module_loader.on': True,
		'tools.al_module_loader.name': 'ALTextToSpeech',
	}

	def POST(self):
		req = cherrypy.request
		text = req.body.read()
		req.module.say(text)

class Memory(BaseHandler):
	_cp_config = {
		'tools.al_module_loader.on': True,
		'tools.al_module_loader.name': 'ALMemory',
	}

	def GET(self, name):
		cherrypy.response.headers['Content-Type'] = 'application/json'
		return json.dumps(cherrypy.request.module.getData(name))

class Root(BaseHandler):
	behaviors = Behaviors()
	audio = AudioDevice()
	speech = TextToSpeech()
	memory = Memory()

	def GET(self):
		return 'Welcome to <a href="controller">NAO</a>'

this_dir = os.path.dirname(__file__)

def start():
	config = {
		'global': {
			'server.socket_host': '0.0.0.0',
			'server.socket_port': 8080,
			'engine.autoreload.on': False,
		},
		'/': {
			'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
			'tools.trailing_slash.status': 307,
		},
		'/controller': {
			'tools.staticfile.on': True,
			'tools.staticfile.filename': os.path.join(this_dir,
				'controller.xhtml')
		},
		'/assets': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': os.path.join(this_dir, 'assets'),
		},
		# okapi is a tool for working with RESTful web services
		'/okapi': {
			'tools.staticfile.on': True,
			'tools.staticfile.filename': os.path.join(this_dir, 'okapi.html')
		},
		'/okapibg.png': {
			'tools.staticfile.on': True,
			'tools.staticfile.filename': os.path.join(this_dir, 'okapibg.png')
		},
	}
	if hasattr(cherrypy.engine, 'signal_handler'):
		cherrypy.engine.signal_handler.subscribe()
	if hasattr(cherrypy.engine, 'console_control_handler'):
		cherrypy.engine.console_control_handler.subscribe()
	cherrypy.config.update(config)
	cherrypy.tree.mount(Root(), config=config)
	cherrypy.engine.start()
	tts = naoqi.ALProxy("ALTextToSpeech", 'localhost', 9559)
	#tts.say("Cherry Nao engaged")

def stop():
	cherrypy.engine.exit()

if __name__ == '__main__':
	start()
	cherrypy.engine.block()
	stop()
