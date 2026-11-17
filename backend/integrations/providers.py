"""
Every service Adion can connect to. All of them use the same "Connect" button (OAuth 2.0); the owner adds each service's client ID
and secret once on the Owner tab, then every user just presses Connect.

Adding a service = adding one entry here. Keys:
  auth_url / token_url / scopes        the OAuth endpoints and what to ask for
  scope_param, scope_sep               how the scopes are sent (Slack: 'user_scope' + comma)
  extra_auth                           extra query parameters for the authorize page
  pkce                                 send a PKCE challenge
  token_auth                           'post' (client id/secret in the body) or 'basic' (HTTP Basic); token_json = send JSON instead of a form
  token_path                           where the access token sits in the answer when it is nested (Slack)
  userinfo_url/_method, label_keys     how to find the account's e-mail/name (shown in the list); token_label_keys = look in the token answer
  api                                  {name: base URL}: the only addresses Adion may call for this service
  api_headers                          headers the service wants on every call
  caps                                 'mail' and 'calendar' get dedicated tools (adapters.py); everything else uses the generic service_api tool
  safe_post                            POST paths that only READ (do not need approval): Notion search, Dropbox listings...
  graphql                              POST bodies are GraphQL: queries are reads, mutations need approval
  review                               a note when the service must approve the app before other people can use it
"""

PROVIDERS = {
    'google': {
        'name': 'Google (Gmail, Calendar, Drive, Docs, Sheets, Tasks)', 'group': 'Mail & calendar',
        'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth', 'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://openidconnect.googleapis.com/v1/userinfo', 'label_keys': ['email'],
        'scopes': ['openid', 'email', 'https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send',
                   'https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents',
                   'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/tasks'],
        'extra_auth': {'access_type': 'offline', 'prompt': 'consent'}, 'pkce': True, 'caps': ['mail', 'calendar'],
        'api': {'gmail': 'https://gmail.googleapis.com/gmail/v1/users/me', 'calendar': 'https://www.googleapis.com/calendar/v3',
                'drive': 'https://www.googleapis.com/drive/v3', 'docs': 'https://docs.googleapis.com/v1', 'sheets': 'https://sheets.googleapis.com/v4',
                'tasks': 'https://tasks.googleapis.com/tasks/v1'},
        'console': 'https://console.cloud.google.com/apis/credentials',
        'setup': ['Open console.cloud.google.com, create a project and enable the Gmail, Calendar, Drive, Docs, Sheets and Tasks APIs.',
                  'Set up the OAuth consent screen (External is fine) and add yourself as a test user.',
                  'Create Credentials > OAuth client ID > Web application.', 'Add the Redirect URI shown here, then paste the Client ID and secret.'],
        'review': 'Google may show an "unverified app" screen for your own account; that is normal while the app is in test mode.',
    },
    'microsoft': {
        'name': 'Microsoft (Outlook, Calendar, OneDrive, To Do)', 'group': 'Mail & calendar',
        'auth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize', 'token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        'userinfo_url': 'https://graph.microsoft.com/v1.0/me', 'label_keys': ['mail', 'userPrincipalName'],
        'scopes': ['offline_access', 'openid', 'email', 'User.Read', 'Mail.ReadWrite', 'Mail.Send', 'Calendars.ReadWrite', 'Files.ReadWrite', 'Tasks.ReadWrite'],
        'extra_auth': {'prompt': 'select_account'}, 'pkce': True, 'caps': ['mail', 'calendar'],
        'api': {'graph': 'https://graph.microsoft.com/v1.0'},
        'console': 'https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade',
        'setup': ['Open Microsoft Entra > App registrations > New registration (any directory and personal accounts).',
                  'Add the Redirect URI shown here as a "Web" redirect.', 'Under Certificates & secrets create a client secret.',
                  'Paste the Application (client) ID and the secret value here.'],
    },
    'github': {
        'name': 'GitHub (repos, issues, pull requests)', 'group': 'Developer',
        'auth_url': 'https://github.com/login/oauth/authorize', 'token_url': 'https://github.com/login/oauth/access_token',
        'userinfo_url': 'https://api.github.com/user', 'label_keys': ['login'], 'scopes': ['repo', 'read:user', 'user:email'], 'pkce': False,
        'api': {'github': 'https://api.github.com'}, 'api_headers': {'Accept': 'application/vnd.github+json'},
        'console': 'https://github.com/settings/developers',
        'setup': ['Open github.com/settings/developers > OAuth Apps > New OAuth App.', 'Set "Authorization callback URL" to the Redirect URI shown here.',
                  'Create the app, generate a client secret, and paste the Client ID and secret here.'],
    },
    'slack': {
        'name': 'Slack (read and post messages)', 'group': 'Chat',
        'auth_url': 'https://slack.com/oauth/v2/authorize', 'token_url': 'https://slack.com/api/oauth.v2.access', 'scope_param': 'user_scope', 'scope_sep': ',',
        'scopes': ['channels:read', 'channels:history', 'groups:read', 'groups:history', 'im:read', 'im:history', 'mpim:read', 'mpim:history', 'chat:write',
                   'users:read', 'search:read'],
        'pkce': False, 'token_path': 'authed_user', 'token_label_keys': ['team.name'], 'api': {'slack': 'https://slack.com/api'},
        'console': 'https://api.slack.com/apps',
        'setup': ['Open api.slack.com/apps > Create New App > From scratch.', 'Under OAuth & Permissions add the Redirect URL shown here.',
                  'Add the User Token Scopes listed in the Connect screen (channels, chat:write, search:read...).', 'Paste the Client ID and Client Secret (Basic Information) here.'],
    },
    'notion': {
        'name': 'Notion (pages and databases)', 'group': 'Notes & tasks',
        'auth_url': 'https://api.notion.com/v1/oauth/authorize', 'token_url': 'https://api.notion.com/v1/oauth/token', 'scopes': [],
        'extra_auth': {'owner': 'user'}, 'pkce': False, 'token_auth': 'basic', 'token_json': True, 'token_label_keys': ['workspace_name'],
        'api': {'notion': 'https://api.notion.com/v1'}, 'api_headers': {'Notion-Version': '2022-06-28'}, 'safe_post': ['/search', '/databases/'],
        'console': 'https://www.notion.so/my-integrations',
        'setup': ['Open notion.so/my-integrations > New integration, type "Public".', 'Add the Redirect URI shown here.', 'Paste the OAuth client ID and secret here.'],
    },
    'todoist': {
        'name': 'Todoist (tasks)', 'group': 'Notes & tasks',
        'auth_url': 'https://todoist.com/oauth/authorize', 'token_url': 'https://todoist.com/oauth/access_token', 'scopes': ['data:read_write', 'data:delete'],
        'scope_sep': ',', 'pkce': False, 'api': {'todoist': 'https://api.todoist.com/rest/v2'}, 'console': 'https://developer.todoist.com/appconsole.html',
        'setup': ['Open developer.todoist.com/appconsole.html > Create a new app.', 'Set the OAuth redirect URL to the Redirect URI shown here.', 'Paste the Client ID and secret here.'],
    },
    'asana': {
        'name': 'Asana (projects and tasks)', 'group': 'Notes & tasks',
        'auth_url': 'https://app.asana.com/-/oauth_authorize', 'token_url': 'https://app.asana.com/-/oauth_token', 'scopes': [], 'pkce': True,
        'userinfo_url': 'https://app.asana.com/api/1.0/users/me', 'label_keys': ['data.email'], 'api': {'asana': 'https://app.asana.com/api/1.0'},
        'console': 'https://app.asana.com/0/my-apps',
        'setup': ['Open app.asana.com/0/my-apps > Create new app.', 'Add the Redirect URI shown here.', 'Paste the Client ID and secret here.'],
    },
    'linear': {
        'name': 'Linear (issues)', 'group': 'Notes & tasks',
        'auth_url': 'https://linear.app/oauth/authorize', 'token_url': 'https://api.linear.app/oauth/token', 'scopes': ['read', 'write'], 'scope_sep': ',',
        'pkce': False, 'api': {'linear': 'https://api.linear.app'}, 'graphql': True, 'console': 'https://linear.app/settings/api',
        'setup': ['Open linear.app/settings/api > OAuth applications > New.', 'Add the Redirect URI shown here.', 'Paste the Client ID and secret here.'],
    },
    'dropbox': {
        'name': 'Dropbox (files)', 'group': 'Files',
        'auth_url': 'https://www.dropbox.com/oauth2/authorize', 'token_url': 'https://api.dropboxapi.com/oauth2/token',
        'scopes': ['account_info.read', 'files.metadata.read', 'files.content.read', 'files.content.write'], 'extra_auth': {'token_access_type': 'offline'}, 'pkce': True,
        'userinfo_url': 'https://api.dropboxapi.com/2/users/get_current_account', 'userinfo_method': 'POST', 'label_keys': ['email'],
        'api': {'dropbox': 'https://api.dropboxapi.com/2'},
        'safe_post': ['/files/list_folder', '/files/get_metadata', '/files/search_v2', '/users/get_current_account', '/sharing/list_shared_links'],
        'console': 'https://www.dropbox.com/developers/apps',
        'setup': ['Open dropbox.com/developers/apps > Create app (Scoped access).', 'Add the Redirect URI shown here and enable the file scopes.', 'Paste the App key and secret here.'],
    },
    'spotify': {
        'name': 'Spotify (playback and playlists)', 'group': 'Media',
        'auth_url': 'https://accounts.spotify.com/authorize', 'token_url': 'https://accounts.spotify.com/api/token', 'token_auth': 'basic', 'pkce': True,
        'scopes': ['user-read-email', 'user-read-playback-state', 'user-modify-playback-state', 'user-library-read', 'playlist-read-private', 'playlist-modify-private'],
        'userinfo_url': 'https://api.spotify.com/v1/me', 'label_keys': ['email', 'display_name'], 'api': {'spotify': 'https://api.spotify.com/v1'},
        'console': 'https://developer.spotify.com/dashboard',
        'setup': ['Open developer.spotify.com/dashboard > Create app.', 'Add the Redirect URI shown here.', 'Paste the Client ID and secret here.'],
    },
    'zoom': {
        'name': 'Zoom (meetings)', 'group': 'Mail & calendar',
        'auth_url': 'https://zoom.us/oauth/authorize', 'token_url': 'https://zoom.us/oauth/token', 'token_auth': 'basic', 'scopes': [], 'pkce': True,
        'userinfo_url': 'https://api.zoom.us/v2/users/me', 'label_keys': ['email'], 'api': {'zoom': 'https://api.zoom.us/v2'},
        'console': 'https://marketplace.zoom.us/develop/create',
        'setup': ['Open marketplace.zoom.us > Develop > Build App > OAuth.', 'Add the Redirect URL shown here and the meeting scopes.', 'Paste the Client ID and secret here.'],
    },
    'linkedin': {
        'name': 'LinkedIn (profile and posts)', 'group': 'Social',
        'auth_url': 'https://www.linkedin.com/oauth/v2/authorization', 'token_url': 'https://www.linkedin.com/oauth/v2/accessToken',
        'scopes': ['openid', 'profile', 'email', 'w_member_social'], 'pkce': False, 'userinfo_url': 'https://api.linkedin.com/v2/userinfo', 'label_keys': ['email', 'name'],
        'api': {'linkedin': 'https://api.linkedin.com'}, 'api_headers': {'X-Restli-Protocol-Version': '2.0.0'}, 'console': 'https://www.linkedin.com/developers/apps',
        'setup': ['Open linkedin.com/developers/apps > Create app.', 'Under Products add "Sign In with LinkedIn using OpenID Connect" and "Share on LinkedIn".',
                  'Add the Redirect URL shown here, then paste the Client ID and secret.'],
    },
    'x': {
        'name': 'X / Twitter (read and post)', 'group': 'Social',
        'auth_url': 'https://twitter.com/i/oauth2/authorize', 'token_url': 'https://api.twitter.com/2/oauth2/token', 'token_auth': 'basic', 'pkce': True,
        'scopes': ['tweet.read', 'tweet.write', 'users.read', 'offline.access'], 'userinfo_url': 'https://api.twitter.com/2/users/me', 'label_keys': ['data.username'],
        'api': {'x': 'https://api.twitter.com/2'}, 'console': 'https://developer.x.com/en/portal/dashboard',
        'setup': ['Open developer.x.com > your project > User authentication settings (OAuth 2.0, Web App).', 'Add the Redirect URI shown here.',
                  'Paste the Client ID and Client Secret here.'],
        'review': 'Posting and reading may need a paid X API plan.',
    },
    'facebook': {
        'name': 'Facebook & Instagram (pages)', 'group': 'Social',
        'auth_url': 'https://www.facebook.com/v19.0/dialog/oauth', 'token_url': 'https://graph.facebook.com/v19.0/oauth/access_token', 'scope_sep': ',', 'pkce': False,
        'scopes': ['public_profile', 'email', 'pages_show_list', 'pages_read_engagement', 'pages_manage_posts', 'instagram_basic', 'instagram_content_publish'],
        'userinfo_url': 'https://graph.facebook.com/v19.0/me?fields=name,email', 'label_keys': ['email', 'name'], 'api': {'facebook': 'https://graph.facebook.com/v19.0'},
        'console': 'https://developers.facebook.com/apps',
        'setup': ['Open developers.facebook.com/apps > Create app (Business).', 'Add "Facebook Login" and the Redirect URI shown here.', 'Paste the App ID and App secret here.'],
        'review': 'Meta must review the app before people other than you can use the page and Instagram permissions.',
    },
}

DEFAULTS = {'scope_param': 'scope', 'scope_sep': ' ', 'extra_auth': {}, 'pkce': True, 'token_auth': 'post', 'token_json': False, 'token_path': '',
            'userinfo_url': '', 'userinfo_method': 'GET', 'label_keys': [], 'token_label_keys': [], 'api_headers': {}, 'caps': [], 'safe_post': [],
            'graphql': False, 'review': '', 'console': '', 'setup': [], 'group': 'Other'}
for _p in PROVIDERS.values():
    for _k, _v in DEFAULTS.items():
        _p.setdefault(_k, _v)
