
import gst
from pitivi.elements.titlesrc import TitleSource
from pitivi.factories.base import SourceFactory
from pitivi.stream import VideoStream

id = 0

def make_id():
    global id
    id += 1
    return id - 1

class TitleSourceFactory(SourceFactory):
    def __init__(self, **kw):
        SourceFactory.__init__(self, "title://%d" % make_id(),
            kw['text'])

        caps = gst.Caps('video/x-raw-yuv; video/x-raw-rgb')
        self.addOutputStream(VideoStream(caps))
        self.source_kw = kw
        self.default_duration = 5 * gst.SECOND
        self.filter_caps = None

    def _makeDefaultBin(self):
        return self._makeStreamBin(self.output_streams[0])

    def _makeStreamBin(self, output_stream=None):
        # The project should have told us what its caps are.
        assert self.filter_caps

        bin = gst.Bin()
        bin.src = TitleSource(**self.source_kw)
        pad = bin.src.get_pad('src')
        pad.set_caps(self.filter_caps)

        bin.queue = gst.element_factory_make("queue", "internal-queue")
        bin.queue.props.max_size_bytes = 0
        bin.queue.props.max_size_time = 0
        #bin.queue.props.max_size_buffers = 3
        if not output_stream.has_alpha():
            csp = gst.element_factory_make("ffmpegcolorspace",
                "internal-colorspace")
        elif output_stream.videotype == 'video/x-raw-rgb':
            csp = gst.element_factory_make("alphacolor",
                "internal-alphacolor")
        else:
            csp = gst.element_factory_make("identity")
        #csp = gst.element_factory_make('alphacolor')
        bin.freeze = gst.element_factory_make("imagefreeze")
        bin.alpha = gst.element_factory_make("alpha", "internal-alpha")
        try:
            bin.alpha.props.prefer_passthrough = True
        except AttributeError:
            self.warning("User has old version of alpha. prefer-passthrough not enabled")
        bin.alpha.set_property('alpha',0)
        bin.scale = gst.element_factory_make('videoscale','internal-scale')
        capsfilter = gst.element_factory_make('capsfilter')
        capsfilter.props.caps = output_stream.caps.copy()
        identity = gst.element_factory_make('identity')
        identity.set_property('single-segment',True)

        bin.add(bin.src,bin.queue,csp, bin.freeze, bin.alpha,bin.scale, capsfilter,identity)
        gst.element_link_many(bin.src,bin.queue, csp, bin.alpha,bin.scale, bin.freeze,capsfilter,identity)

        target = identity.get_pad('src')
        ghost = gst.GhostPad('src', target)
        bin.add_pad(ghost)

        return bin

    def setFilterCaps(self, caps):
        assert not caps.is_empty()
        assert caps[0].has_field('width')
        assert caps[0].has_field('height')
        # All we really care about is getting the resolution right; other
        # elements will take care of the other aspects.
        self.filter_caps = gst.Caps('video/x-raw-rgb,depth=32,bpp=32')
        self.filter_caps[0]['width'] = caps[0]['width']
        self.filter_caps[0]['height'] = caps[0]['height']

        for bin in self.bins:
            pad = bin.src.get_pad('src')
            pad.set_caps(self.filter_caps)

    def _releaseBin(self, bin):
        pass

    def set(self, **props):
        self.source_kw.update(props)
        self.name = self.source_kw['text']

        for bin in self.bins:
            bin.src.__dict__.update(props)

            # This is hacky but gets the job done.
            #
            # ImageFreeze throws its cached buffer away on the flush start,
            # but we also need to make the source restart its task. The source
            # is PAUSED because ImageFreeze returns FLOW_WRONG_STATE after it
            # gets the buffer. It seems the source doesn't restart its task
            # after PAUSED -> PLAYING, unless it's been to READY first.
            #
            # Doing the state change without doing a flush first makes it hang
            # for some reason.

            sinkpad = bin.freeze.get_pad('sink')

            event = gst.event_new_flush_start()
            sinkpad.send_event(event)
            event = gst.event_new_flush_stop()
            sinkpad.send_event(event)

            bin.set_state(gst.STATE_READY)
            bin.set_state(gst.STATE_PLAYING)

