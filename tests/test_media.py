import io
import struct
import unittest
from unittest.mock import Mock, patch

from gi.repository import GLib

from minimonitor.album_art import Artwork, load_art
from minimonitor.media import Mpris, Track, make_track
from minimonitor.media_device import Device, values
from minimonitor.media_keys import Chords
from minimonitor.music_render import render_music
from minimonitor.screens import Screens


class MediaTest(unittest.TestCase):
    def test_selection_and_track_data(self):
        bus = Mock()
        bus.call_sync.side_effect = [
            GLib.Variant("(as)", (["org.mpris.MediaPlayer2.a", "not-a-player"],)),
            GLib.Variant("(s)", (":1.10",)),
            GLib.Variant("(a{sv})", ({
                "PlaybackStatus": GLib.Variant("s", "Playing"),
                "Metadata": GLib.Variant("a{sv}", {"xesam:title": GLib.Variant("s", "A")},
                ),
                "Position": GLib.Variant("x", 2_000_000),
            },)),
        ]
        observer = Mpris(Mock(), bus=bus)
        self.addCleanup(observer.close)
        track = observer.active()
        self.assertEqual(track.title, "A")
        self.assertEqual(track.elapsed(track.sampled_at + 1), 3_000_000)
        observer._owner_changed(None, None, None, None, None,
                                GLib.Variant("(sss)", (track.player, ":1.10", "")))
        self.assertIsNone(observer.active())
        self.assertEqual(make_track("x", {}, None, 0).title, "Faixa desconhecida")

    @patch("minimonitor.screens.GLib.source_remove")
    @patch("minimonitor.screens.GLib.timeout_add", return_value=1)
    def test_automatic_switch_grace_and_manual_toggle(self, timeout, _remove):
        clock = Mock(return_value=0)
        output = Mock()
        screens = Screens(lambda: "dashboard frame", lambda track, now: track.title, output, clock=clock)
        screens.changed(None)
        output.assert_called_with("dashboard", "dashboard frame")
        playing = Track("a", title="Faixa", status="Playing")
        screens.changed(playing)
        output.assert_called_with("music", "Faixa")
        self.assertEqual(timeout.call_args.args[0], 1000)
        screens.toggle()
        screens.changed(playing)
        self.assertEqual(screens.active, "dashboard")
        screens.toggle()
        clock.return_value = 1
        screens.changed(None)
        clock.return_value = 30
        screens.refresh()
        self.assertEqual(screens.active, "music")
        clock.return_value = 31
        screens.refresh()
        self.assertEqual(screens.active, "dashboard")

    def test_chords_do_not_toggle_or_repeat(self):
        toggle, skip, pause = Mock(), Mock(), Mock()
        chords = Chords(186, toggle, skip, pause)
        for key, value in [
            (186, 1), (105, 1), (105, 2), (186, 0),
            (186, 1), (57, 1), (57, 2), (57, 0), (186, 0),
            (57, 1), (57, 0), (186, 1), (186, 0),
        ]:
            chords.event(key, value)
        skip.assert_called_once_with("left")
        pause.assert_called_once_with()
        toggle.assert_called_once_with()

    def test_pause_and_resume_the_active_or_recent_player(self):
        observer = Mpris.__new__(Mpris)
        spotify = Track("spotify", status="Playing")
        vlc = Track("vlc", status="Paused")
        observer.tracks = {"spotify": spotify, "vlc": vlc}
        observer.recent = {"spotify": 10, "vlc": 5}
        with patch.object(observer, "_control", return_value=True) as control:
            self.assertTrue(observer.toggle_playback("vlc"))
            control.assert_called_once_with(spotify, "CanPause", "Pause")
            observer.tracks["spotify"] = Track("spotify", status="Paused")
            self.assertTrue(observer.toggle_playback())
            control.assert_called_with(observer.tracks["spotify"], "CanPlay", "Play")
            observer.tracks.clear()
            self.assertFalse(observer.toggle_playback())
            self.assertEqual(control.call_count, 2)

    def test_render_and_cached_fallback(self):
        track = Track("a", title="faixa " * 60, status="Playing", duration=5_000_000)
        frame = render_music(track, 1)
        image = io.BytesIO()
        frame.write_to_png(image)
        self.assertEqual(struct.unpack(">II", image.getvalue()[16:24]), (240, 240))
        self.assertIsNone(load_art("invalid:cover"))
        art = Artwork(Mock())
        self.addCleanup(art.close)
        art.cache["invalid:cover"] = None
        with patch.object(art.worker, "submit") as download:
            self.assertIsNone(art.get("invalid:cover"))
            download.assert_not_called()

    def test_serial_page_switch_and_incremental_updates(self):
        device = Device(7)
        track = Track("a", title="Faixa", status="Playing", duration=10_000_000)
        with patch.object(device, "write_registers") as write:
            device.display("music", values(track, 5))
            self.assertEqual(write.call_args_list[0].args[0], bytes.fromhex("80000200000006"))
            self.assertEqual(write.call_count, 6)
            device.display("music", values(track, 5))
            self.assertEqual(write.call_count, 6)
            device.display("music", values(track, 6))
            self.assertEqual(write.call_count, 8)


    def test_visualizer_runs_only_during_playback(self):
        track = Track("a", status="Playing", duration=20_000_000)
        self.assertNotEqual(values(track, 2)[1][1], values(track, 3)[1][1])
        paused = Track("a", status="Paused", duration=20_000_000)
        self.assertEqual(values(paused, 3)[1][1], 0)
        device = Device(7, visualizer=True)
        with patch.object(device, "write_registers") as write:
            device.display("music", values(track, 2))
            self.assertEqual(write.call_count, 6)
            payload = write.call_args.args[0]
            self.assertEqual(payload[0], 0x81)
            self.assertEqual(struct.unpack(">HIHI", payload[1:]), (2224, 1, 2225, 3))


if __name__ == "__main__":
    unittest.main()
