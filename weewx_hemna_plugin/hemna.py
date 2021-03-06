import re
import sys
import syslog
import time
import Queue
import urllib
import urllib2

import weewx
from weewx import restx
# from weeutil import weeutil


class StdHemna(restx.StdRESTful):

    archive_url = 'http://wx.hemna.com/'

    def __init__(self, engine, config_dict):
        super(StdHemna, self).__init__(engine, config_dict)

        self.archive_queue = Queue.Queue()

        _manager_dict = weewx.manager.get_manager_dict_from_config(
            config_dict, 'wx_binding')

        _ambient_dict = restx.get_site_dict(config_dict, 'Hemna', 'station',
                                            'password')
        _ambient_dict.setdefault('server_url', self.archive_url)

        self.archive_thread = HemnaThread(
            self.archive_queue, _manager_dict,
            protocol_name="Hemna", **_ambient_dict)
        self.archive_thread.start()
        self.bind(weewx.NEW_ARCHIVE_RECORD, self.new_archive_record)

        self.cached_values = restx.CachedValues()
        self.loop_queue = Queue.Queue()
        self.loop_thread = HemnaThread(
            self.loop_queue, _manager_dict, protocol_name="Hemna",
            **_ambient_dict)
        self.loop_thread.start()
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

    def new_archive_record(self, event):
        syslog.syslog(syslog.LOG_DEBUG, "hemna: raw record: %s" % event.record)
        self.archive_queue.put(event.record)

    def new_loop_packet(self, event):
        syslog.syslog(syslog.LOG_DEBUG, "hemna: raw packet: %s" % event.packet)
        self.cached_values.update(event.packet, event.packet['dateTime'])
        syslog.syslog(syslog.LOG_DEBUG, "hemna: cached packet: %s" %
                      self.cached_values.get_packet(event.packet['dateTime']))
        self.loop_queue.put(
            self.cached_values.get_packet(event.packet['dateTime']))


class HemnaThread(restx.RESTThread):

    # Types and formats of the data to be published:
    _FORMATS = {'dateTime': 'datetime=%s',
                'barometer': 'rel_pressure=%.3f',
                'outTemp': 'temp_out=%.1f',
                'inTemp': 'temp_in=%.1f',
                'outHumidity': 'rel_hum_out=%.0f',
                'inHumidity': 'rel_hum_in=%.0f',
                'windSpeed': 'wind_speed=%.1f',
                'windDir': 'wind_angle=%.0f',
                'windchill': 'wind_chill=%.1f',
                'dewpoint': 'dewpoint=%.1f',
                'rainTotal': 'rain_total=%.2f',
                'hourRain': 'rain_1h=%.2f',
                'dayRain': 'rain_24h=%.2f'}

    def __init__(self, queue, manager_dict, station, password, server_url,
                 protocol_name="Hemna", post_interval=None,
                 max_backlog=sys.maxint, stale=None, log_success=True,
                 log_failure=True, timeout=10, max_tries=3, retry_wait=5,
                 softwaretype='weewx-%s' % weewx.__version__,
                 skip_upload=False):

        super(HemnaThread, self).__init__(queue,
                                          protocol_name=protocol_name,
                                          manager_dict=manager_dict,
                                          post_interval=post_interval,
                                          max_backlog=max_backlog,
                                          stale=stale,
                                          log_success=log_success,
                                          log_failure=log_failure,
                                          timeout=timeout,
                                          max_tries=max_tries,
                                          retry_wait=retry_wait,
                                          softwaretype=softwaretype,
                                          skip_upload=skip_upload)

        self.station = station
        self.password = password
        self.server_url = server_url
        self.formats = HemnaThread._FORMATS

    def format_url(self, record):
        """Return an URL for posting using WOW's version of the Ambient
        protocol."""

        _liststr = ["target=remote-update"]

        # Go through each of the supported types, formatting it, then adding
        # to _liststr:
        for _key in HemnaThread._FORMATS:
            _v = record.get(_key)
            # Check to make sure the type is not null
            if _v is not None:
                if _key == 'dateTime':
                    # _v = urllib.quote_plus(
                    # datetime.datetime.utcfromtimestamp(_v).isoformat(' '))
                    # _v = urllib.quote_plus(weeutil.timestamp_to_string(_v))
                    format_str = "%Y-%m-%d %H:%M:%S"
                    date_str = time.strftime(format_str, time.localtime(_v))
                    _v = urllib.quote_plus(date_str)
                # Format the value, and accumulate in _liststr:
                _liststr.append(HemnaThread._FORMATS[_key] % _v)
            else:
                _liststr.append(HemnaThread._FORMATS[_key] % float(0))

        # wind angle
        _liststr.append("wind_direction=N")
        # T = record.get('outTemp')
        # V = record.get('windSpeed')
        # wind_chill = 35.74 + (0.6215*T) - 35.75*(V**0.16) +0.4275*T*(V**0.16)
        # _liststr.append("wind_chill=%.1f" % wind_chill)
        # _liststr.append("rain_total=0.00")
        _liststr.append("tendency=na")
        _liststr.append("forecast=na")

        # Now stick all the pieces together with an ampersand between them:
        _urlquery = '&'.join(_liststr)
        # This will be the complete URL for the HTTP GET:
        _url = "%s?%s" % (self.server_url, _urlquery)
        # show the url in the logs for debug, but mask any password
        if weewx.debug >= 2:
            syslog.syslog(syslog.LOG_DEBUG, "restx: HEMNA: url: %s" %
                          re.sub(r"siteAuthenticationKey=[^\&]*",
                                 "siteAuthenticationKey=XXX", _url))
        return _url

    def post_request(self, request, payload=None):  # @UnusedVariable
        """Version of post_request() for the WOW protocol, which
        uses a response error code to signal a bad login."""
        try:
            try:
                _response = urllib2.urlopen(request, timeout=self.timeout)
            except TypeError:
                _response = urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            # WOW signals a bad login with a HTML Error 400 or 403 code:
            if e.code == 400 or e.code == 403:
                raise restx.BadLogin(e)
            else:
                raise
        else:
            return _response
