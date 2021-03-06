"""
Nginx-rtmp-module stat parser.

Need to install nginx-rtmp-module first.
"""
import xml.dom.minidom
import urllib2

if __package__ is None:
    from utils import error_exit
else:
    from .utils import error_exit


STAT_URL = "http://127.0.0.1:8080/stat"


def pass_for_node_value(root, node_name):
    child = root.getElementsByTagName(node_name)

    if len(child) >= 1 and child[0].firstChild:
        return child[0].firstChild.data

    return 0


class MetaInfo(object):
    def __init__(self):
        self.video_width = None
        self.video_height = None
        self.video_frame_rate = None
        self.video_codec = None
        self.video_profile = None
        self.video_compat = None
        self.video_level = None
        self.audio_codec = None
        self.audio_profile = None
        self.audio_channels = None
        self.audio_sample_rate = None

    def parse_info(self, meta_root):
        video_child = meta_root.getElementsByTagName('video')[0]
        self.video_width = int(pass_for_node_value(video_child, 'width'))
        self.video_height = int(pass_for_node_value(video_child, 'height'))
        self.video_frame_rate = int(pass_for_node_value(video_child, 'frame_rate'))
        self.video_codec = pass_for_node_value(video_child, 'codec')
        self.video_profile = pass_for_node_value(video_child, 'profile')
        self.video_compat = int(pass_for_node_value(video_child, 'compat'))
        self.video_level = float(pass_for_node_value(video_child, 'level'))

        audio_child = meta_root.getElementsByTagName('audio')[0]
        self.audio_codec = pass_for_node_value(audio_child, 'codec')
        self.audio_profile = pass_for_node_value(audio_child, 'profile')
        self.audio_channels = int(pass_for_node_value(audio_child, 'channels'))
        self.audio_sample_rate = int(pass_for_node_value(audio_child, 'sample_rate'))

    def print_info(self, output):
        output.append('\t\tVideo Meta: width %d, height %d, frame_rate %d, codec %s, profile %s, compat %d, level %f' %
                      (self.video_width, self.video_height, self.video_frame_rate, self.video_codec, self.video_profile,
                       self.video_compat, self.video_level))
        output.append('\t\tAudio Meta: codec %s, profile %s, channels %d, sample rate %d' %
                      (self.audio_codec, self.audio_profile, self.audio_channels, self.audio_sample_rate))


class ClientInfo(object):
    def __init__(self, client_root):
        self.id = int(pass_for_node_value(client_root, 'id'))
        self.address = pass_for_node_value(client_root, 'address')
        self.time = int(pass_for_node_value(client_root, 'time'))
        self.flashver = pass_for_node_value(client_root, 'flashver')

        self.pageurl = None
        self.swfurl = None

        self.dropped = int(pass_for_node_value(client_root, 'dropped'))
        self.avsync = int(pass_for_node_value(client_root, 'avsync'))
        self.timestamp = int(pass_for_node_value(client_root, 'timestamp'))

        self.is_publisher = False

    def parse_info(self, client_root):
        publish_child = client_root.getElementsByTagName('publishing')
        if publish_child.length > 0:
            self.is_publisher = True

        if not self.is_publisher:
            self.pageurl = pass_for_node_value(client_root, 'pageurl')
            self.swfurl = pass_for_node_value(client_root, 'swfurl')

    def print_info(self, output):
        if self.is_publisher:
            output.append('\t\tServer: addr %s, flashver %s' % (self.address, self.flashver))
        else:
            output.append('\t\tClient: addr %s, flashver %s, page %s, swf %s' %
                          (self.address, self.flashver, self.pageurl, self.swfurl))


class StreamInfo(object):
    def __init__(self, stream_root):
        self.name = pass_for_node_value(stream_root, 'name')
        self.time = int(pass_for_node_value(stream_root, 'time'))
        self.bw_in = int(pass_for_node_value(stream_root, 'bw_in'))
        self.bytes_in = int(pass_for_node_value(stream_root, 'bytes_in'))
        self.bw_out = int(pass_for_node_value(stream_root, 'bw_out'))
        self.bytes_out = int(pass_for_node_value(stream_root, 'bytes_out'))
        self.bw_audio = int(pass_for_node_value(stream_root, 'bw_audio'))
        self.bw_video = int(pass_for_node_value(stream_root, 'bw_video'))
        self.nclients = int(pass_for_node_value(stream_root, 'nclients'))

        self.meta_info = None
        self.clients = {}

    def parse_info(self, stream_root):
        meta_child = stream_root.getElementsByTagName('meta')
        if meta_child.length > 0:
            self.meta_info = MetaInfo()
            self.meta_info.parse_info(meta_child[0])

        client_child = stream_root.getElementsByTagName('client')
        for client in client_child:
            client_info = ClientInfo(client)
            client_info.parse_info(client)
            self.clients[client_info.id] = client_info

    def print_info(self, output):
        output.append('\tStream %s: time %d, bw_in %d, bytes_in %f, bw_out %d, '
                      'bytes_out %f, bw_audio %d, bs_video %d, clients %d' %
                      (self.name, self.time, self.bw_in, self.bytes_in, self.bw_out,
                       self.bytes_out, self.bw_audio, self.bw_video, self.nclients))

        output.append('\tMeta info:')
        if self.meta_info:
            self.meta_info.print_info(output)
        else:
            output.append('\t\tStream Idel')

        output.append('\t\tClient Info:')
        for client in self.clients.itervalues():
            client.print_info(output)


class NginxRtmpInfo(object):
    def __init__(self, arguments):
        self.arguments = arguments
        self.processor = None

        self.rtmp_url = STAT_URL
        self.nginx_version = None
        self.rtmp_version = None
        self.compiler = None
        self.built = None
        self.pid = None
        self.uptime = None
        self.accepted = None
        self.bw_in = None
        self.bw_out = None
        self.bytes_in = None
        self.bytes_out = None

        self.stream_infos = {}

    def set_processor(self, processor):
        self.processor = processor

    def get_rtmp_url(self):
        rtmp_url = self.arguments['--rtmp-stat-url']
        if rtmp_url:
            self.rtmp_url = rtmp_url
        return self.rtmp_url

    def processor_process(self):
        if self.processor is None:
            return

        records = {}
        for stream_info in self.stream_infos.itervalues():
            records['request'] = stream_info.name
            records['in_bytes'] = stream_info.bytes_in
            records['in_bw'] = stream_info.bw_in
            records['out_bytes'] = stream_info.bytes_out
            records['out_bw'] = stream_info.bw_out

            for client in stream_info.clients.itervalues():
                records['remote_addr'] = client.address
                records['time'] = client.time
                records['http_user_agent'] = client.flashver
                self.processor.process(records)

    def parse_info(self):
        self.get_rtmp_url()
        try:
            response = urllib2.urlopen(self.rtmp_url)
        except urllib2.URLError:
            error_exit('Cannot access RTMP URL: %s' % self.rtmp_url)

        dom = xml.dom.minidom.parseString(response.read())
        root = dom.documentElement

        self.nginx_version = pass_for_node_value(root, 'nginx_version')
        self.rtmp_version = pass_for_node_value(root, 'nginx_rtmp_version')
        self.compiler = pass_for_node_value(root, 'compiler')
        self.built = pass_for_node_value(root, 'built')
        self.pid = int(pass_for_node_value(root, 'pid'))
        self.uptime = int(pass_for_node_value(root, 'uptime'))
        self.accepted = int(pass_for_node_value(root, 'naccepted'))
        self.bw_in = int(pass_for_node_value(root, 'bw_in'))
        self.bw_out = int(pass_for_node_value(root, 'bw_out'))
        self.bytes_in = int(pass_for_node_value(root, 'bytes_in'))
        self.bytes_out = int(pass_for_node_value(root, 'bytes_out'))

        live_child = root.getElementsByTagName('server')[0].getElementsByTagName(
            'application')[0].getElementsByTagName('live')[0]
        for stream_child in live_child.getElementsByTagName('stream'):
            stream_info = StreamInfo(stream_child)
            stream_info.parse_info(stream_child)
            self.stream_infos[stream_info.name] = stream_info

        self.processor_process()

    def print_info(self):
        output = list()
        output.append('Summary:')
        output.append('\tNginx version: %s, RTMP version: %s, Compiler: %s, Built: %s, PID: %d, Uptime: %ds.' %
                      (self.nginx_version, self.rtmp_version, self.compiler, self.built, self.pid, self.uptime))
        output.append('\tAccepted: %d, bw_in: %f Kbit/s, bytes_in: %02f MByte, '
                      'bw_out: %02f Kbit/s, bytes_out: %02f MByte' %
                      (self.accepted, self.bw_in / 1024.0, self.bytes_in / 1024.0 / 1024,
                       self.bw_out / 1024.0, self.bytes_out / 1024.0 / 1024))

        output.append('Detail:')
        output.append('\tStreams: %d' % len(self.stream_infos))
        for stream in self.stream_infos.itervalues():
            stream.print_info(output)

        return output
