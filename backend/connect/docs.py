"""Integration guides, written per app with the client's own public key and address already filled in."""

PLATFORMS = [('web', 'Website (any)'), ('react', 'React / Next.js'), ('react-native', 'React Native (mobile)'), ('api', 'Any platform (REST API)'),
             ('actions', 'Letting Adion do things')]


def _tickets(base, app):
    return f'''## 1. Tell Adion who the signed-in user is (on YOUR server)

Never put the secret key (`sk_...`) in the website or mobile app. Your server asks Adion for a short-lived **ticket** for the user who is
signed in, and gives it to the app. If nobody is signed in, skip the ticket: Adion then only shares public information.

**Node.js**
```js
// POST /adion-ticket  (your own endpoint, only for signed-in users)
const r = await fetch("{base}/api/connect/v1/tickets", {{
  method: "POST",
  headers: {{ "Authorization": "Bearer " + process.env.ADION_SECRET_KEY, "Content-Type": "application/json" }},
  body: JSON.stringify({{ userId: user.id, name: user.name }}),
}});
const {{ ticket }} = await r.json();   // send `ticket` to your app
```

**Python**
```python
r = requests.post("{base}/api/connect/v1/tickets",
    headers={{"Authorization": "Bearer " + ADION_SECRET_KEY}}, json={{"userId": user.id, "name": user.name}})
ticket = r.json()["ticket"]
```

**curl**
```bash
curl -X POST {base}/api/connect/v1/tickets -H "Authorization: Bearer sk_YOUR_SECRET_KEY" -H "Content-Type: application/json" -d '{{"userId":"42","name":"Asha"}}'
```
'''


def guide(app, platform, base):
    pk = app.public_key
    head = f'# Connect Adion to **{app.name}**\n\nYour public key: `{pk}`  \nAdion address: `{base}`\n\n'
    allowed = ', '.join(app.allowed_origins) or '(none yet: add your website address under Access & rules)'
    if platform == 'web':
        return head + f'''## Add the assistant to any website

Paste this before `</body>`:

```html
<script src="{base}/api/connect/widget.js"></script>
<script>
  Adion.init({{
    key: "{pk}",
    // For signed-in users: ask YOUR server for a ticket (see step 2). Leave out for visitors.
    getTicket: async () => (await fetch("/adion-ticket", {{ method: "POST" }}).then(r => r.json())).ticket,
    // Only if your API uses the user's own login token (API connection):
    getUserToken: () => localStorage.getItem("access_token"),
  }});
</script>
```

Allowed websites for this key: **{allowed}**. A website that is not on the list cannot use the key.

You can run actions in your own page code, with nothing sent to Adion:
```js
Adion.registerAction("add_transaction", async ({{ amount, category }}) => {{
  return await myApp.addTransaction(amount, category);   // your own code and your own login
}});
```

{_tickets(base, app)}'''
    if platform == 'react':
        return head + f'''## React / Next.js

1. Add the script once (Next.js: in `app/layout.tsx` use `<Script src="{base}/api/connect/widget.js" strategy="afterInteractive" />`).
2. Start it when your user is known:

```tsx
'use client';
import {{ useEffect }} from 'react';

declare global {{ interface Window {{ Adion?: any }} }}

export default function AdionAssistant({{ user }}: {{ user?: {{ id: string }} }}) {{
  useEffect(() => {{
    const t = setInterval(() => {{
      if (!window.Adion) return;
      clearInterval(t);
      window.Adion.init({{
        key: '{pk}',
        getTicket: user ? async () => (await fetch('/api/adion-ticket', {{ method: 'POST' }}).then(r => r.json())).ticket : undefined,
        getUserToken: () => localStorage.getItem('access_token') ?? '',
      }});
      window.Adion.registerAction('add_transaction', async (args: any) => myAddTransaction(args)); // optional
    }}, 200);
    return () => clearInterval(t);
  }}, [user]);
  return null;
}}
```

Next.js ticket route (`app/api/adion-ticket/route.ts`):
```ts
export async function POST() {{
  const user = await getSignedInUser();               // your own auth
  if (!user) return Response.json({{ error: 'not signed in' }}, {{ status: 401 }});
  const r = await fetch('{base}/api/connect/v1/tickets', {{
    method: 'POST',
    headers: {{ Authorization: 'Bearer ' + process.env.ADION_SECRET_KEY!, 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ userId: user.id, name: user.name }}),
  }});
  return Response.json(await r.json());
}}
```

Allowed websites: **{allowed}**
'''
    if platform == 'react-native':
        return head + f'''## React Native

Mobile apps send no website address, so keep **"Allow mobile apps"** switched on under Access & rules. Copy this component into your app
(it needs no extra packages):

```tsx
import React, {{ useRef, useState }} from 'react';
import {{ View, Text, TextInput, TouchableOpacity, FlatList, ActivityIndicator }} from 'react-native';

const BASE = '{base}/api/connect/v1';
const KEY = '{pk}';
type Handler = (args: any) => Promise<any>;
export const actions: Record<string, Handler> = {{}};          // actions.add_transaction = async (args) => ...
type Msg = {{ role: 'user' | 'assistant'; text: string }};

async function post(path: string, body: any) {{
  const r = await fetch(BASE + path, {{ method: 'POST', headers: {{ Authorization: 'Bearer ' + KEY, 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || 'Request failed');
  return j;
}}

export default function AdionChat({{ getTicket, getUserToken }}: {{ getTicket?: () => Promise<string>; getUserToken?: () => Promise<string> }}) {{
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<any[]>([]);
  const conv = useRef('');

  async function ids() {{ return {{ ticket: getTicket ? await getTicket() : undefined, userToken: getUserToken ? await getUserToken() : undefined, conversationId: conv.current || undefined }}; }}

  async function handle(res: any) {{
    conv.current = res.conversationId;
    if (res.reply) setMsgs(m => [...m, {{ role: 'assistant', text: res.reply }}]);
    const open = res.pending || [];
    // actions that run inside THIS app (nothing is sent to Adion except the result)
    const results: any[] = [];
    for (const p of open.filter((x: any) => x.kind === 'client' && !x.needsConfirm)) {{
      try {{ results.push({{ callId: p.callId, result: await actions[p.name](p.args) }}); }} catch (e: any) {{ results.push({{ callId: p.callId, error: String(e?.message || e) }}); }}
    }}
    if (results.length) return handle(await post('/chat/result', {{ ...(await ids()), results }}));
    setPending(open);
  }}

  async function send() {{
    const t = text.trim(); if (!t || busy) return;
    setText(''); setMsgs(m => [...m, {{ role: 'user', text: t }}]); setBusy(true);
    try {{ await handle(await post('/chat', {{ ...(await ids()), message: t }})); }}
    catch (e: any) {{ setMsgs(m => [...m, {{ role: 'assistant', text: e.message }}]); }}
    setBusy(false);
  }}

  async function decide(p: any, approve: boolean) {{
    setPending([]); setBusy(true);
    try {{
      if (p.kind === 'client' && approve) {{
        let d: any;
        try {{ d = {{ callId: p.callId, result: await actions[p.name](p.args) }}; }} catch (e: any) {{ d = {{ callId: p.callId, error: String(e?.message || e) }}; }}
        await handle(await post('/chat/result', {{ ...(await ids()), results: [d] }}));
      }} else {{
        await handle(await post('/chat/confirm', {{ ...(await ids()), decisions: [{{ callId: p.callId, approve }}] }}));
      }}
    }} catch (e: any) {{ setMsgs(m => [...m, {{ role: 'assistant', text: e.message }}]); }}
    setBusy(false);
  }}

  return (
    <View style={{{{ flex: 1 }}}}>
      <FlatList data={{msgs}} keyExtractor={{(_, i) => String(i)}} renderItem={{({{ item }}) => (
        <View style={{{{ alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start', backgroundColor: item.role === 'user' ? '#0891b2' : '#1e293b', margin: 6, padding: 10, borderRadius: 14, maxWidth: '85%' }}}}>
          <Text style={{{{ color: 'white' }}}}>{{item.text}}</Text></View>)}} />
      {{pending.filter(p => p.needsConfirm).map(p => (
        <View key={{p.callId}} style={{{{ margin: 8, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: '#f59e0b' }}}}>
          <Text style={{{{ color: 'white', marginBottom: 8 }}}}>Please confirm: {{p.summary}}</Text>
          <View style={{{{ flexDirection: 'row', gap: 8 }}}}>
            <TouchableOpacity onPress={{() => decide(p, true)}}><Text style={{{{ color: '#34d399' }}}}>Confirm</Text></TouchableOpacity>
            <TouchableOpacity onPress={{() => decide(p, false)}}><Text style={{{{ color: '#fb7185' }}}}>Cancel</Text></TouchableOpacity>
          </View>
        </View>))}}
      {{busy && <ActivityIndicator />}}
      <View style={{{{ flexDirection: 'row', padding: 8 }}}}>
        <TextInput value={{text}} onChangeText={{setText}} onSubmitEditing={{send}} placeholder="Ask anything about the app" placeholderTextColor="#94a3b8" style={{{{ flex: 1, color: 'white', borderWidth: 1, borderColor: '#334155', borderRadius: 10, padding: 10 }}}} />
        <TouchableOpacity onPress={{send}} style={{{{ justifyContent: 'center', padding: 10 }}}}><Text style={{{{ color: '#22d3ee' }}}}>Send</Text></TouchableOpacity>
      </View>
    </View>
  );
}}
```

Use it: `<AdionChat getTicket={{async () => (await myServer.post('/adion-ticket')).ticket}} getUserToken={{async () => session.access_token}} />`

Register actions that run inside your app: `actions.add_transaction = async ({{ amount, category }}) => addTransaction(amount, category);`

For voice, use your platform's speech packages (for example `expo-speech` to speak the replies and `@react-native-voice/voice` to listen), and send the recognised text to `send()`.

{_tickets(base, app)}'''
    if platform == 'api':
        return head + f'''## REST API (any language or platform)

All calls: `Authorization: Bearer {pk}` (the public key) and JSON bodies. Browsers must come from an allowed website (**{allowed}**); mobile and server apps send no website address.

| Call | Purpose |
|---|---|
| `POST /api/connect/v1/tickets` (secret key) | your server asks for a ticket for a signed-in user: `{{userId, name}}` -> `{{ticket}}` |
| `GET /api/connect/v1/config` | app name, greeting, language |
| `POST /api/connect/v1/chat` | `{{message, ticket?, userToken?, conversationId?}}` -> `{{reply, lang, conversationId, pending[]}}` |
| `POST /api/connect/v1/chat/confirm` | `{{conversationId, ticket?, userToken?, decisions:[{{callId, approve}}]}}` |
| `POST /api/connect/v1/chat/result` | `{{conversationId, ticket?, results:[{{callId, result | error}}]}}` after your app ran an action |
| `GET /api/connect/v1/conversations?ticket=...` | the signed-in user's own conversations |

`pending` lists things waiting: `kind: "confirm"` = show the user `summary` and call `/chat/confirm`; `kind: "client"` = run the action in your app and
call `/chat/result`. Anything the user changes always needs their confirmation.

{_tickets(base, app)}'''
    return head + f'''## Letting Adion do things in your app

Adion can read and change data **only through actions you define**, and only for the signed-in user.

**Option A: API connection (from your API documentation).** In the portal, open **Actions** and import your OpenAPI/Swagger file or Postman
collection. Adion turns every endpoint into an action (switched off until you enable it). Under **Access & rules** set:
- the API address of your server (https only);
- how Adion logs in: **the user's own token** (the app passes it with each chat as `userToken`, Adion uses it only for that request and never stores it),
  or a fixed header such as an API key you give Adion.

**Option B: In-app actions (nothing leaves your app).** Register a function in your app (see the Website, React or React Native guide).
Adion only says "run `add_transaction` with these values"; your own code and your own login do the work.

**Access level** (per app): *Limited* = read-only actions, *Standard* = also changes, *Complete* = also risky ones such as delete. Changes and risky
actions **always ask the user to confirm** first, showing the exact values.

**Hidden fields:** for every action you can list response fields Adion must never see. Anything that looks like a password, token, PIN, card number or
key is removed automatically.

Tip: write a clear description for each action ("Adds a money transaction. amount is in rupees"). Adion reads it to decide when to use the action.
'''
