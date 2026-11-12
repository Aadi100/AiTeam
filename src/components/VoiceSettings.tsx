'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { X, Play, Globe2, Cloud, Laptop, Mic } from 'lucide-react';
import { api } from '@/lib/api';
import { useVoice } from '@/context/VoiceContext';
import { STYLES, STT_LANGS, guessGender, type Style } from '@/lib/voice';

interface NaturalVoice { id: string; name: string; lang: string; locale: string; gender: 'female' | 'male' }
interface Lang { code: string; name: string; count: number }

const chip = (on: boolean, disabled = false) =>
  `rounded-full border px-3 py-1 text-xs transition ${disabled ? 'opacity-40 cursor-not-allowed border-slate-800 text-slate-500' : on ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100' : 'border-slate-700 text-slate-300 hover:border-cyan-500 cursor-pointer'}`;

export default function VoiceSettings() {
  const { voiceSettingsOpen, setVoiceSettingsOpen, voicePrefs: p, setVoicePrefs, voiceStatus, previewVoice, isSpeaking, stopSpeaking } = useVoice();
  const [voices, setVoices] = useState<NaturalVoice[]>([]);
  const [langs, setLangs] = useState<Lang[]>([]);
  const [loadErr, setLoadErr] = useState('');
  const [query, setQuery] = useState('');
  const [deviceVoices, setDeviceVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (!voiceSettingsOpen) return;
    api<{ voices: NaturalVoice[]; languages: Lang[] }>('/voice/voices').then(r => { setVoices(r.voices); setLangs(r.languages); setLoadErr(''); })
      .catch(e => setLoadErr(e instanceof Error ? e.message : 'Could not load the voices'));
    if ('speechSynthesis' in window) {
      const load = () => setDeviceVoices(window.speechSynthesis.getVoices());
      load();
      window.speechSynthesis.addEventListener?.('voiceschanged', load);
      return () => window.speechSynthesis.removeEventListener?.('voiceschanged', load);
    }
  }, [voiceSettingsOpen]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const names = new Map(langs.map(l => [l.code, l.name]));
    const out = new Map<string, NaturalVoice[]>();
    for (const v of voices) {
      const lname = names.get(v.lang) || v.lang;
      if (q && !lname.toLowerCase().includes(q) && !v.name.toLowerCase().includes(q) && !v.locale.toLowerCase().includes(q)) continue;
      out.set(lname, [...(out.get(lname) || []), v]);
    }
    return [...out.entries()];
  }, [voices, langs, query]);

  if (!voiceSettingsOpen) return null;
  const natural = p.engine === 'natural';
  const chosen = voices.find(v => v.id === p.voice);
  const previewLang = natural ? (chosen?.lang || (p.sttLang !== 'auto' ? p.sttLang.split('-')[0] : 'en')) : (deviceVoices.find(v => v.name === p.browserVoice)?.lang.split('-')[0] || 'en');

  return (
    <div className="fixed inset-0 z-[60] bg-black/60 flex items-center justify-center p-4" onClick={() => setVoiceSettingsOpen(false)}>
      <div className="w-full max-w-lg max-h-[92vh] overflow-y-auto rounded-2xl border border-slate-800 bg-slate-950 p-5 space-y-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold flex items-center gap-2"><Mic className="h-4 w-4 text-cyan-300" /> Voice settings</h2>
          <button onClick={() => setVoiceSettingsOpen(false)} className="text-slate-400 hover:text-white"><X className="h-4 w-4" /></button>
        </div>

        {/* engine */}
        <div>
          <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Voice engine</p>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => setVoicePrefs({ engine: 'natural' })} disabled={voiceStatus ? !voiceStatus.natural : false}
              className={`text-left rounded-xl border p-3 transition ${natural ? 'border-cyan-400 bg-cyan-500/10' : 'border-slate-800 hover:border-slate-600'} disabled:opacity-40`}>
              <span className="flex items-center gap-1.5 text-sm text-slate-100"><Cloud className="h-4 w-4 text-cyan-300" /> Natural</span>
              <span className="block text-[11px] text-slate-400 mt-1">{voiceStatus?.natural === false ? 'Not reachable right now (no internet?)' : '300+ lifelike voices, 75 languages, male and female. The text I speak is sent to Microsoft’s online speech service.'}</span>
            </button>
            <button onClick={() => setVoicePrefs({ engine: 'browser' })} className={`text-left rounded-xl border p-3 transition ${!natural ? 'border-cyan-400 bg-cyan-500/10' : 'border-slate-800 hover:border-slate-600'}`}>
              <span className="flex items-center gap-1.5 text-sm text-slate-100"><Laptop className="h-4 w-4 text-slate-300" /> This device</span>
              <span className="block text-[11px] text-slate-400 mt-1">Private and works offline, but fewer languages and a more robotic sound. No style effects.</span>
            </button>
          </div>
        </div>

        {/* voice */}
        <div className="space-y-2">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Voice</p>
          {natural ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <button onClick={() => setVoicePrefs({ voice: '' })} className={chip(!p.voice)}>Automatic</button>
                <span className="text-[11px] text-slate-500">picks the best voice for the language I answer in</span>
              </div>
              {!p.voice && (
                <div className="flex gap-2 items-center">
                  <span className="text-xs text-slate-400">Prefer</span>
                  <button onClick={() => setVoicePrefs({ gender: 'female' })} className={chip(p.gender === 'female')}>Female</button>
                  <button onClick={() => setVoicePrefs({ gender: 'male' })} className={chip(p.gender === 'male')}>Male</button>
                </div>
              )}
              <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search a language or voice (Hindi, Urdu, Arabic, Aria…)"
                className="w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500" />
              {loadErr && <p className="text-[11px] text-rose-300">{loadErr}</p>}
              <select value={p.voice} onChange={e => setVoicePrefs({ voice: e.target.value })} size={7}
                className="w-full rounded-lg bg-slate-900 border border-slate-700 px-1 py-1 text-xs outline-none focus:border-cyan-500">
                <option value="">Automatic</option>
                {groups.map(([lname, vs]) => (
                  <optgroup key={lname} label={lname}>
                    {vs.map(v => <option key={v.id} value={v.id}>{v.name} · {v.gender} · {v.locale}</option>)}
                  </optgroup>
                ))}
              </select>
              <p className="text-[11px] text-slate-500">A voice you pick is used when it speaks the language of my answer; otherwise I switch to the best voice for that language so I always speak yours.</p>
            </>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <button onClick={() => setVoicePrefs({ browserVoice: '' })} className={chip(!p.browserVoice)}>Automatic</button>
                <button onClick={() => setVoicePrefs({ gender: 'female' })} className={chip(p.gender === 'female')}>Female</button>
                <button onClick={() => setVoicePrefs({ gender: 'male' })} className={chip(p.gender === 'male')}>Male</button>
              </div>
              <select value={p.browserVoice} onChange={e => setVoicePrefs({ browserVoice: e.target.value })} size={6}
                className="w-full rounded-lg bg-slate-900 border border-slate-700 px-1 py-1 text-xs outline-none focus:border-cyan-500">
                <option value="">Automatic</option>
                {deviceVoices.map(v => <option key={v.name} value={v.name}>{v.name} · {v.lang}{guessGender(v.name) ? ` · ${guessGender(v.name)}` : ''}</option>)}
              </select>
              {deviceVoices.length === 0 && <p className="text-[11px] text-amber-300">This browser reported no voices yet. Try again in a moment, or use Natural.</p>}
            </>
          )}
        </div>

        {/* style */}
        <div>
          <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Style</p>
          <div className="flex flex-wrap gap-1.5">
            {STYLES.map(s => (
              <button key={s.id} title={s.hint} disabled={!natural && s.id !== 'normal'} onClick={() => setVoicePrefs({ style: s.id as Style })} className={chip(p.style === s.id, !natural && s.id !== 'normal')}>{s.label}</button>
            ))}
          </div>
          <p className="mt-1 text-[11px] text-slate-500">{STYLES.find(s => s.id === p.style)?.hint}. Styles play on top of any Natural voice.</p>
        </div>

        {/* sliders */}
        <div className="grid grid-cols-2 gap-4">
          <label className="text-xs text-slate-300">Speed {p.rate.toFixed(2)}×
            <input type="range" min={0.6} max={1.5} step={0.05} value={p.rate} onChange={e => setVoicePrefs({ rate: Number(e.target.value) })} className="w-full accent-cyan-500" />
          </label>
          <label className="text-xs text-slate-300">Pitch {p.pitch > 0 ? '+' : ''}{p.pitch}
            <input type="range" min={-30} max={30} step={2} value={p.pitch} onChange={e => setVoicePrefs({ pitch: Number(e.target.value) })} className="w-full accent-cyan-500" />
          </label>
        </div>

        <button onClick={() => (isSpeaking ? stopSpeaking() : previewVoice(previewLang))}
          className="flex items-center gap-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 px-4 py-2 text-xs font-medium transition">
          <Play className="h-3.5 w-3.5" /> {isSpeaking ? 'Stop' : 'Test this voice'}
        </button>

        {/* what you speak */}
        <div className="border-t border-slate-800 pt-4 space-y-2">
          <p className="text-[11px] uppercase tracking-wider text-slate-500 flex items-center gap-1.5"><Globe2 className="h-3.5 w-3.5" /> The language I listen in</p>
          <select value={p.sttLang} onChange={e => setVoicePrefs({ sttLang: e.target.value })}
            className="w-full rounded-lg bg-slate-900 border border-slate-700 px-2 py-2 text-xs outline-none focus:border-cyan-500">
            <option value="auto" disabled={voiceStatus ? !voiceStatus.whisper : false}>Any language, detected automatically (runs offline on this PC){voiceStatus && !voiceStatus.whisper ? ' - not installed' : ''}</option>
            {STT_LANGS.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}
          </select>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            {p.sttLang === 'auto'
              ? 'Press the mic and speak in any language. After you stop talking, I work out which language it was (it takes a few seconds) and answer in the same language. The first time, a speech model of about 140 MB is downloaded.'
              : 'Fast, live recognition in the language you chose. Switch to “any language” if you mix languages.'}
            {' '}I always <b>reply in the language you used</b>, and the wake word “Adion” is listened for in English.
          </p>
          {voiceStatus && !voiceStatus.whisper && <p className="text-[11px] text-amber-300">Any-language listening needs <code>pip install faster-whisper</code> on the backend.</p>}
        </div>

        <p className="text-[11px] text-slate-500 leading-relaxed border-t border-slate-800 pt-3">
          Celebrity or actor voices are not available: copying a real person’s voice needs their permission and is not offered by free voice tools. The male, female, robot, deep, radio and other styles above are what I can do.
        </p>
      </div>
    </div>
  );
}
