import os
import json
import io

import six
import cherrypy

from PIL import Image

try:
	import naoqi
except ImportError:
	from mocks import naoqi

class BaseHandler(object):
	exposed = True

def load_al_module(name):
	"""
	Add a proxy to the AL Module named by `name` to the CherryPy request.
	"""
	cherrypy.serving.request.module = naoqi.ALProxy(name, 'localhost', 9559)

# install the AL Module Loader as a CherryPy tool.
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


class Grouped(object):
	"mix-in for grouping behaviors"

	@classmethod
	def grouped_behaviors(cls, raw_behaviors):
		aug_behaviors = map(GroupedBehavior, raw_behaviors)
		return [behavior.__json__() for behavior in aug_behaviors]


class InstalledBehaviors(Grouped, BaseHandler):
	def GET(self):
		req = cherrypy.request
		resp = cherrypy.response
		resp.headers['Content-Type'] = 'application/json'
		res = self.grouped_behaviors(req.module.getInstalledBehaviors())
		return json.dumps(res)


class GroupedBehavior(six.text_type):
	"""
	Take a qualified behavior name and provide
	group and name attributes for each of the parts.

	>>> gb = GroupedBehavior('naos-life-channel/sit-scratch')
	>>> gb.name
	'sit-scratch'
	>>> gb.group
	'naos-life-channel'

	If no group is provided, it will be None
	>>> gb = GroupedBehavior('canidance')
	>>> gb.name
	'canidance'
	>>> gb.group
	"""

	@property
	def name(self):
		group, sep, name = self.rpartition('/')
		return name

	@property
	def group(self):
		group, sep, name = self.rpartition('/')
		return group or None

	def __json__(self):
		return dict(
			name=self.name,
			group=self.group,
			qual_name=self,
		)


class RunningBehaviors(Grouped, BaseHandler):

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

class Behaviors(Grouped, BaseHandler):
	_cp_config = {
		'tools.al_module_loader.on': True,
		'tools.al_module_loader.name': 'ALBehaviorManager',
	}
	installed = InstalledBehaviors()
	running = RunningBehaviors()

	def GET(self):
		req = cherrypy.request
		resp = cherrypy.response
		resp.headers['Content-Type'] = 'application/json'
		res = self.grouped_behaviors(req.module.getInstalledBehaviors())
		return json.dumps(res)

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
	"A base handler for the ALAudioDevice"

	_cp_config = {
		'tools.al_module_loader.on': True,
		'tools.al_module_loader.name': 'ALAudioDevice',
	}

	volume = AudioVolume()

class VideoImage(BaseHandler):

	def GET(self):
		resolution = 2    # VGA
		colorspace = 11   # RGB
		fps = 1
		client_id = cherrypy.request.module.subscribe(
			"Cherry NAO", resolution, colorspace, fps)

		(
			width,
			height,
			n_layers,
			colorspace,
			ts_sec, ts_msec, # timestamp
			bytes,
			camera_id,
			left_angle, top_angle,
			right_angle, bottom_angle
		) = cherrypy.request.module.getImageRemote(client_id)

		cherrypy.request.module.unsubscribe(client_id)

		# Convert the image to PNG using PIL
		image = Image.fromstring("RGB", (width, height), bytes)

		cherrypy.response.headers['Content-Type'] = 'image/png'
		out_stream = io.BytesIO()

		image.save(out_stream, "PNG")
		out_stream.seek(0)

		return out_stream

class VideoDevice(BaseHandler):
	"A base handler for the ALVideoDevice"

	_cp_config = {
		'tools.al_module_loader.on': True,
		'tools.al_module_loader.name': 'ALVideoDevice',
	}

	image = VideoImage()

class TextToSpeech(BaseHandler):
	"A handler for ALTextToSpeech"

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
	video = VideoDevice()

	def GET(self):
		"Provide a simple link to the controller"
		return 'Welcome to <a href="controller">NAO</a>'

this_dir = os.path.dirname(__file__)

def start():
	config = {
		'global': {
			'server.socket_host': '::0',
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

def stop():
	cherrypy.engine.exit()

if __name__ == '__main__':
	start()
	cherrypy.engine.block()
	stop()
