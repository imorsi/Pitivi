
import cairo
import pango
import pangocairo
import gobject
import gst
import urllib

class TitleSource(gst.BaseSrc):
    __gsttemplates__ = (
        gst.PadTemplate("src",
                        gst.PAD_SRC,
                        gst.PAD_ALWAYS,
                        #gst.Caps("video/x-raw-rgb,depth=24,bpp=32"))
                        # XXX: hardcoded width and height
                        gst.Caps("video/x-raw-rgb,depth=32,bpp=32,width=720,height=576"))
    )
    def __init__(self, text='title',
            font='Sans',
            text_size=128,
            x_alignment=0.5,
            y_alignment=0.5,
            bg_color=None,
            fg_color=None,
        layout_alignment='left'):
        gst.BaseSrc.__init__(self)
        self.start = 0
        self.stop = gst.CLOCK_TIME_NONE
        self.curpos = 0
        # let's put the granularity at 10 msgs per second
        self.granularity = gst.SECOND / 10
        self.set_live(False)
        self.set_format(gst.FORMAT_TIME)

        self.text = text
        self.font = font
        self.text_size = text_size
        self.x_alignment = x_alignment
        self.y_alignment = y_alignment
        self.bg_color = bg_color if bg_color is not None else (0, 0, 0 , 0)
        self.fg_color = fg_color 
        self.layout_alignment = pango.ALIGN_LEFT
        if layout_alignment == 'right':
            self.layout_alignment = pango.ALIGN_RIGHT
        elif layout_alignment == 'center':
            self.layout_alignment = pango.ALIGN_CENTER

    def do_create(self, offset, size):
        gst.debug("offset: %r, size:%r" % (offset, size))

        pad = self.get_pad('src')
        caps = pad.get_negotiated_caps()

        assert caps[0].has_field('width')
        assert caps[0].has_field('height')
        width, height = caps[0]['width'], caps[0]['height']
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)

        # background
        #if self.bg_color is not None:
        cr.set_source_rgba(*self.bg_color)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # text - color will be determined by font style instead
        #if self.fg_color is not None:
        # cr.set_source_rgba(*self.fg_color)
        pcr = pangocairo.CairoContext(cr)
        layout = pcr.create_layout()
        layout.set_font_description(
            pango.FontDescription("%s %d" % (self.font, self.text_size)))
        self.text = urllib.unquote(self.text)
        safeText = self.text.replace('<br>','\n').replace('&nbsp;',' ')
        #safeText = self.bg_color
        #layout.set_width = width
        layout.set_markup(safeText)
        layout.set_single_paragraph_mode(False)
        #layout.set_width(width)
        #layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_alignment(self.layout_alignment)
        (ink, (x_bearing, y_bearing, t_width, t_height)) = \
            layout.get_pixel_extents()
        x = (width - t_width) * self.x_alignment - x_bearing
        y = (height - t_height) * self.y_alignment - y_bearing
        cr.move_to(x, y)
        pcr.show_layout(layout)

        b = gst.Buffer(surface.get_data())
        b.timestamp = self.curpos
        b.duration = self.granularity
        self.curpos += b.duration
        gst.debug("timestamp:%s" % gst.TIME_ARGS(b.timestamp))
        gst.debug("duration:%s" % gst.TIME_ARGS(b.duration))
        # set timestamps
        return gst.FLOW_OK, b

    def do_is_seekable(self):
        return True

    # FIXME : implement seeking
    def do_do_seek(self, segment):
        gst.debug("start %r stop %r" % (segment.start,
                                        segment.stop))
        self.start = segment.start
        self.curpos = segment.start
        self.stop = segment.stop
        return True

gobject.type_register(TitleSource)

