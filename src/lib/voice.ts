// Adion's voice: preferences, voice picking, sentence splitting and sound styles (robot, deep, radio...).

export type Style = 'normal' | 'robot' | 'deep' | 'radio' | 'echo' | 'chipmunk';

export interface VoicePrefs {
  engine: 'natural' | 'browser';   // natural = Microsoft neural voices (online, 75 languages); browser = this device's own voices
  voice: string;                   // natural voice id, or '' = automatic (best voice for the language you are speaking)
  browserVoice: string;            // device voice name, or '' = automatic
  gender: 'female' | 'male';       // used by automatic selection
  style: Style;
  rate: number;                    // 0.6 - 1.5
  pitch: number;                   // -30 .. +30 (Hz offset for natural voices)
  sttLang: string;                 // 'auto' (any language, offline Whisper) or a BCP-47 tag for the browser's recogniser
}

export const DEFAULT_PREFS: VoicePrefs = { engine: 'natural', voice: '', browserVoice: '', gender: 'female', style: 'normal', rate: 1, pitch: 0, sttLang: 'auto' };
const KEY = 'adion.voice.v3';

export function loadPrefs(): VoicePrefs {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { ...DEFAULT_PREFS, ...(JSON.parse(raw) as Partial<VoicePrefs>) };
  } catch { /* private mode */ }
  return DEFAULT_PREFS;
}
export function savePrefs(p: VoicePrefs) {
  try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* ignore */ }
}

export const STYLES: { id: Style; label: string; hint: string }[] = [
  { id: 'normal', label: 'Normal', hint: 'The voice as it is' },
  { id: 'robot', label: 'Robot', hint: 'Metallic, like a machine' },
  { id: 'deep', label: 'Deep', hint: 'Lower and slower, cinematic' },
  { id: 'radio', label: 'Radio', hint: 'Old walkie-talkie' },
  { id: 'echo', label: 'Echo', hint: 'In a big hall' },
  { id: 'chipmunk', label: 'Chipmunk', hint: 'High and fast' },
];

// what you can speak to Adion (browser recogniser). "Auto" is the offline Whisper path and understands ~100 languages.
export const STT_LANGS: { code: string; name: string }[] = [
  { code: 'en-US', name: 'English (US)' }, { code: 'en-GB', name: 'English (UK)' }, { code: 'en-IN', name: 'English (India)' },
  { code: 'hi-IN', name: 'Hindi' }, { code: 'ur-PK', name: 'Urdu' }, { code: 'ar-SA', name: 'Arabic' }, { code: 'bn-BD', name: 'Bengali' },
  { code: 'pa-IN', name: 'Punjabi' }, { code: 'gu-IN', name: 'Gujarati' }, { code: 'mr-IN', name: 'Marathi' }, { code: 'ta-IN', name: 'Tamil' },
  { code: 'te-IN', name: 'Telugu' }, { code: 'kn-IN', name: 'Kannada' }, { code: 'ml-IN', name: 'Malayalam' }, { code: 'fa-IR', name: 'Persian' },
  { code: 'tr-TR', name: 'Turkish' }, { code: 'es-ES', name: 'Spanish' }, { code: 'es-MX', name: 'Spanish (Mexico)' }, { code: 'fr-FR', name: 'French' },
  { code: 'de-DE', name: 'German' }, { code: 'it-IT', name: 'Italian' }, { code: 'pt-BR', name: 'Portuguese (Brazil)' }, { code: 'pt-PT', name: 'Portuguese' },
  { code: 'nl-NL', name: 'Dutch' }, { code: 'ru-RU', name: 'Russian' }, { code: 'uk-UA', name: 'Ukrainian' }, { code: 'pl-PL', name: 'Polish' },
  { code: 'id-ID', name: 'Indonesian' }, { code: 'ms-MY', name: 'Malay' }, { code: 'vi-VN', name: 'Vietnamese' }, { code: 'th-TH', name: 'Thai' },
  { code: 'ja-JP', name: 'Japanese' }, { code: 'ko-KR', name: 'Korean' }, { code: 'zh-CN', name: 'Chinese (Mandarin)' }, { code: 'sw-KE', name: 'Swahili' },
  { code: 'he-IL', name: 'Hebrew' }, { code: 'el-GR', name: 'Greek' }, { code: 'sv-SE', name: 'Swedish' }, { code: 'fil-PH', name: 'Filipino' },
];

// a short sentence per language for the "Test voice" button
export const SAMPLES: Record<string, string> = {
  en: "Hello, I'm Adion. This is how I sound.", hi: 'नमस्ते, मैं आदियन हूँ। मेरी आवाज़ ऐसी लगती है।', ur: 'سلام، میں آدیون ہوں۔ میری آواز ایسی ہے۔',
  ar: 'مرحباً، أنا أديون. هكذا يبدو صوتي.', bn: 'নমস্কার, আমি আদিয়ন। আমার কণ্ঠ এমন শোনায়।', ta: 'வணக்கம், நான் அடியன். என் குரல் இப்படி இருக்கும்.',
  es: 'Hola, soy Adion. Así es como sueno.', fr: "Bonjour, je suis Adion. Voici ma voix.", de: 'Hallo, ich bin Adion. So klinge ich.',
  pt: 'Olá, eu sou o Adion. É assim que eu soo.', it: 'Ciao, sono Adion. Ecco come suono.', ru: 'Здравствуйте, я Адион. Вот как я звучу.',
  ja: 'こんにちは、アディオンです。これが私の声です。', ko: '안녕하세요, 저는 아디온입니다. 제 목소리입니다.', zh: '你好，我是Adion。这就是我的声音。',
  tr: 'Merhaba, ben Adion. Sesim böyle.', id: 'Halo, saya Adion. Beginilah suara saya.', nl: 'Hallo, ik ben Adion. Zo klink ik.',
};

// ───────── device voices ─────────
const FEMALE = /(zira|aria|jenny|hazel|samantha|susan|heera|female|woman|emma|ava|sonia|libby|natasha|neerja|swara|salma|zariyah|uzma|elvira|denise|katja|amelie|paulina|helena|ayumi|yaoyao|sun-hi|google .*female)/i;
const MALE = /(david|mark|guy|ravi|james|male|man|george|ryan|andrew|brian|christopher|eric|roger|steffan|madhur|hamed|salman|jorge|alvaro|conrad|henri|claude|ichiro|yunyang|injoon)/i;
export function guessGender(name: string): 'female' | 'male' | '' {
  if (FEMALE.test(name) && !/\bmale\b/i.test(name)) return 'female';
  if (MALE.test(name)) return 'male';
  return '';
}

export function pickBrowserVoice(voices: SpeechSynthesisVoice[], lang: string, gender: 'female' | 'male', preferred: string): SpeechSynthesisVoice | undefined {
  const pref = voices.find(v => v.name === preferred);
  if (pref && (!lang || pref.lang.toLowerCase().startsWith(lang.toLowerCase()))) return pref;
  const same = voices.filter(v => v.lang.toLowerCase().replace('_', '-').split('-')[0] === lang.toLowerCase());
  const pool = same.length ? same : voices.filter(v => v.lang.toLowerCase().startsWith('en'));
  const score = (v: SpeechSynthesisVoice) => (/natural|online|neural/i.test(v.name) ? 4 : 0) + (guessGender(v.name) === gender ? 2 : 0) + (/google/i.test(v.name) ? 1 : 0) + (v.localService ? 0 : 0.5);
  return [...pool].sort((a, b) => score(b) - score(a))[0] || voices[0];
}

export function splitSentences(text: string, max = 260): string[] {
  const clean = text.replace(/```[\s\S]*?```/g, ' ').replace(/https?:\/\/\S+/g, ' link ').replace(/[*#`_>|~]+/g, ' ').replace(/\[\d+\]/g, ' ').replace(/\s+/g, ' ').trim();
  const parts = clean.match(/[^.!?।۔؟。！？\n]+[.!?।۔؟。！？]*/g) || (clean ? [clean] : []);
  const out: string[] = [];
  for (const p of parts) {
    const s = p.trim();
    if (!s) continue;
    if (s.length <= max) { out.push(s); continue; }
    for (const piece of s.match(new RegExp(`.{1,${max}}(\\s|$)`, 'g')) || [s]) out.push(piece.trim());
  }
  return out;
}

// ───────── sound styles ─────────
/** Plays a decoded clip through an effect chain. `done` resolves when it ends (or is stopped). */
export function playBuffer(ctx: AudioContext, buffer: AudioBuffer, style: Style, volume = 1): { stop: () => void; done: Promise<void> } {
  const src = ctx.createBufferSource();
  src.buffer = buffer;
  const extra: AudioScheduledSourceNode[] = [];
  let out: AudioNode = src;
  if (style === 'deep') {
    src.playbackRate.value = 0.84;
    const shelf = ctx.createBiquadFilter(); shelf.type = 'lowshelf'; shelf.frequency.value = 220; shelf.gain.value = 7;
    src.connect(shelf); out = shelf;
  } else if (style === 'chipmunk') {
    src.playbackRate.value = 1.38;
  } else if (style === 'robot') {
    const mod = ctx.createGain(); mod.gain.value = 0;
    const osc = ctx.createOscillator(); osc.type = 'sine'; osc.frequency.value = 55; osc.connect(mod.gain); osc.start(); extra.push(osc);
    const dry = ctx.createGain(); dry.gain.value = 0.3;
    const mix = ctx.createGain();
    src.connect(mod); src.connect(dry); mod.connect(mix); dry.connect(mix);
    const delay = ctx.createDelay(0.05); delay.delayTime.value = 0.012;
    const fb = ctx.createGain(); fb.gain.value = 0.45;
    mix.connect(delay); delay.connect(fb); fb.connect(delay);
    const sum = ctx.createGain(); mix.connect(sum); delay.connect(sum);
    out = sum;
  } else if (style === 'radio') {
    const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 500;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 3000;
    const shaper = ctx.createWaveShaper();
    const curve = new Float32Array(256);
    for (let i = 0; i < 256; i++) { const x = (i / 128) - 1; curve[i] = Math.tanh(x * 2.2); }
    shaper.curve = curve;
    src.connect(hp); hp.connect(lp); lp.connect(shaper); out = shaper;
  } else if (style === 'echo') {
    const delay = ctx.createDelay(1); delay.delayTime.value = 0.22;
    const fb = ctx.createGain(); fb.gain.value = 0.35;
    const wet = ctx.createGain(); wet.gain.value = 0.45;
    const sum = ctx.createGain();
    src.connect(sum); src.connect(delay); delay.connect(fb); fb.connect(delay); delay.connect(wet); wet.connect(sum);
    out = sum;
  }
  const vol = ctx.createGain(); vol.gain.value = volume;
  out.connect(vol); vol.connect(ctx.destination);
  let finish: () => void = () => {};
  const done = new Promise<void>(res => { finish = res; });
  src.onended = () => { extra.forEach(o => { try { o.stop(); } catch { /* already stopped */ } }); finish(); };
  src.start();
  return { stop: () => { try { src.stop(); } catch { /* not started */ } finish(); }, done };
}
