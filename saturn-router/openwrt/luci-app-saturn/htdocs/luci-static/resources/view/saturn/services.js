'use strict';
'require view';
'require form';
'require uci';
'require ui';
'require rpc';
'require poll';
'require dom';

var saturnStyles = document.createElement('style');
saturnStyles.textContent = [
	':root { color-scheme: light dark; }',
	'.saturn-btn { padding: 6px 16px; border-radius: 4px; font-weight: 500; cursor: pointer; border: 1px solid; }',
	
	'.saturn-btn:disabled { opacity: 0.5; cursor: not-allowed; }',
	'.saturn-btn-start { background-color: #28a745; color: white; border-color: #28a745; }',
	'.saturn-btn-stop { background-color: #6c757d; color: white; border-color: #6c757d; }',
	'.saturn-btn-restart { background-color: #007bff; color: white; border-color: #007bff; }',
	'.saturn-btn-danger { background-color: #dc3545; color: white; border-color: #dc3545; }',
	'@media (prefers-color-scheme: light) {',
	'  .saturn-btn-start { background-color: #198754; border-color: #198754; }',
	'  .saturn-btn-stop { background-color: #5c636a; border-color: #5c636a; }',
	'  .saturn-btn-restart { background-color: #0d6efd; border-color: #0d6efd; }',
	'  .saturn-btn-danger { background-color: #dc3545; border-color: #dc3545; }',
	'}',
	'.saturn-help-text { color: #6c757d; }',
	'@media (prefers-color-scheme: dark) { .saturn-help-text { color: #adb5bd; } }',
	'.cbi-section-table-row + .cbi-section-table-row { border-top: 2px solid #dee2e6; margin-top: 1.5em; padding-top: 1.5em; }',
	'@media (prefers-color-scheme: dark) { .cbi-section-table-row + .cbi-section-table-row { border-color: #495057; } }'
].join('\n');
document.head.appendChild(saturnStyles);

var callTestConnection = rpc.declare({
	object: 'luci.saturn',
	method: 'test_connection',
	params: ['deployment', 'api_type', 'base_url', 'host', 'port', 'api_key'],
	expect: { '': {} }
});

var callGetStatus = rpc.declare({
	object: 'luci.saturn',
	method: 'get_status',
	expect: { '': {} }
});

var callUninstall = rpc.declare({
	object: 'luci.saturn',
	method: 'uninstall',
	expect: { '': {} }
});

var callStart = rpc.declare({
	object: 'luci.saturn',
	method: 'start',
	expect: { '': {} }
});

var callStop = rpc.declare({
	object: 'luci.saturn',
	method: 'stop',
	expect: { '': {} }
});

var callRestart = rpc.declare({
	object: 'luci.saturn',
	method: 'restart',
	expect: { '': {} }
});

var callGetRunningStatus = rpc.declare({
	object: 'luci.saturn',
	method: 'get_running_status',
	expect: { '': {} }
});

var callGetLogs = rpc.declare({
	object: 'luci.saturn',
	method: 'get_logs',
	params: ['lines'],
	expect: { '': {} }
});

var statusData = {};
var runningStatus = { running: false, process_count: 0 };

function getStatusBadge(health, enabled) {
	if (!enabled) {
		return E('span', { 'class': 'badge', 'style': 'background-color:#6c757d;color:white;padding:2px 8px;border-radius:4px;font-size:11px;' }, 'DISABLED');
	}
	switch (health) {
		case 'healthy':
			return E('span', { 'class': 'badge', 'style': 'background-color:#28a745;color:white;padding:2px 8px;border-radius:4px;font-size:11px;' }, '● UP');
		case 'unreachable':
			return E('span', { 'class': 'badge', 'style': 'background-color:#dc3545;color:white;padding:2px 8px;border-radius:4px;font-size:11px;' }, '● DOWN');
		case 'disabled':
			return E('span', { 'class': 'badge', 'style': 'background-color:#6c757d;color:white;padding:2px 8px;border-radius:4px;font-size:11px;' }, 'DISABLED');
		case 'unknown':
			return E('span', { 'class': 'badge', 'style': 'background-color:#ffc107;color:black;padding:2px 8px;border-radius:4px;font-size:11px;' }, '? UNKNOWN');
		default:
			if (health && health.startsWith('error:')) {
				return E('span', { 'class': 'badge', 'style': 'background-color:#fd7e14;color:white;padding:2px 8px;border-radius:4px;font-size:11px;' }, '● ERR ' + health.split(':')[1]);
			}
			return E('span', { 'class': 'badge', 'style': 'background-color:#6c757d;color:white;padding:2px 8px;border-radius:4px;font-size:11px;' }, '...');
	}
}

function updateRunningStatusIndicator() {
	return callGetRunningStatus().then(function(result) {
		if (result) {
			runningStatus = result;
			var badge = document.getElementById('saturn-running-badge');
			if (badge) {
				if (result.running) {
					badge.style.backgroundColor = '#28a745';
					badge.textContent = 'RUNNING (' + result.process_count + ' process' + (result.process_count > 1 ? 'es' : '') + ')';
				} else {
					badge.style.backgroundColor = '#dc3545';
					badge.textContent = 'STOPPED';
				}
			}
		}
	}).catch(function(err) {
		console.error('Failed to get running status:', err);
	});
}

function updateStatusIndicators() {
	return Promise.all([
		callGetStatus().then(function(result) {
			if (result && result.services) {
				result.services.forEach(function(svc) {
					statusData[svc.section] = svc;
					var container = document.getElementById('saturn-status-' + svc.section);
					if (container) {
						dom.content(container, getStatusBadge(svc.health, svc.enabled));
					}
				});
			}
		}),
		updateRunningStatusIndicator()
	]).catch(function(err) {
		console.error('Failed to get status:', err);
	});
}

return view.extend({
	load: function() {
		return Promise.all([
			uci.load('saturn'),
			callGetStatus().then(function(result) {
				if (result && result.services) {
					result.services.forEach(function(svc) {
						statusData[svc.section] = svc;
					});
				}
			}).catch(function() {}),
			callGetRunningStatus().then(function(result) {
				if (result) {
					runningStatus = result;
				}
			}).catch(function() {})
		]);
	},

	render: function() {
		var m, s, o;

		m = new form.Map('saturn', _('Saturn - Network AI Services'),
			_('Configure AI services for zero-config network discovery. ' +
			  'Each service is advertised via mDNS for automatic client discovery.'));

		var serviceControlHtml = E('div', { 'class': 'cbi-section', 'style': 'margin-bottom: 1em;' }, [
			E('h3', {}, _('Service Control')),
			E('div', { 'style': 'display: flex; align-items: center; gap: 1em; flex-wrap: wrap;' }, [
				E('span', { 'style': 'font-weight: bold;' }, _('Status: ')),
				E('span', {
					'id': 'saturn-running-badge',
					'style': 'background-color:' + (runningStatus.running ? '#28a745' : '#dc3545') + ';color:white;padding:4px 12px;border-radius:4px;font-size:12px;font-weight:bold;'
				}, runningStatus.running ? 'RUNNING (' + runningStatus.process_count + ' process' + (runningStatus.process_count > 1 ? 'es' : '') + ')' : 'STOPPED'),
				E('div', { 'style': 'display: flex; gap: 0.5em;' }, [
					E('button', {
						'class': 'saturn-btn saturn-btn-start',
						'id': 'saturn-start-btn',
						'click': function(ev) {
							var btn = ev.target;
							btn.disabled = true;
							btn.textContent = _('Starting...');
							callStart().then(function(result) {
								btn.disabled = false;
								btn.textContent = _('Start');
								if (result.success) {
									ui.addNotification(null, E('p', result.message), 'info');
									updateRunningStatusIndicator();
								} else {
									ui.addNotification(null, E('p', [
										E('strong', _('Error: ')),
										result.error || _('Start failed')
									]), 'error');
								}
							}).catch(function(err) {
								btn.disabled = false;
								btn.textContent = _('Start');
								ui.addNotification(null, E('p', err.message || _('RPC failed')), 'error');
							});
						}
					}, _('Start')),
					E('button', {
						'class': 'saturn-btn saturn-btn-stop',
						'id': 'saturn-stop-btn',
						'click': function(ev) {
							var btn = ev.target;
							btn.disabled = true;
							btn.textContent = _('Stopping...');
							callStop().then(function(result) {
								btn.disabled = false;
								btn.textContent = _('Stop');
								if (result.success) {
									ui.addNotification(null, E('p', result.message), 'info');
									updateRunningStatusIndicator();
								} else {
									ui.addNotification(null, E('p', [
										E('strong', _('Error: ')),
										result.error || _('Stop failed')
									]), 'error');
								}
							}).catch(function(err) {
								btn.disabled = false;
								btn.textContent = _('Stop');
								ui.addNotification(null, E('p', err.message || _('RPC failed')), 'error');
							});
						}
					}, _('Stop')),
					E('button', {
						'class': 'saturn-btn saturn-btn-restart',
						'id': 'saturn-restart-btn',
						'click': function(ev) {
							var btn = ev.target;
							btn.disabled = true;
							btn.textContent = _('Restarting...');
							callRestart().then(function(result) {
								btn.disabled = false;
								btn.textContent = _('Restart');
								if (result.success) {
									ui.addNotification(null, E('p', result.message), 'info');
									updateRunningStatusIndicator();
								} else {
									ui.addNotification(null, E('p', [
										E('strong', _('Error: ')),
										result.error || _('Restart failed')
									]), 'error');
								}
							}).catch(function(err) {
								btn.disabled = false;
								btn.textContent = _('Restart');
								ui.addNotification(null, E('p', err.message || _('RPC failed')), 'error');
							});
						}
					}, _('Restart'))
				])
			]),
			E('p', { 'class': 'saturn-help-text', 'style': 'margin-top: 0.5em; font-size: 12px;' },
				_('Start/Stop controls the saturn-beacon process. Changes to service configuration require Save & Apply followed by Restart.'))
		]);

		s = m.section(form.TypedSection, 'service', _('Services'),
			_('Add AI services to advertise on the network. Lower priority numbers are preferred by clients. ' +
			  'Status refreshes automatically every 10 seconds.'));
		s.addremove = true;
		s.anonymous = true;
		s.addbtntitle = _('Add new service');

		o = s.option(form.DummyValue, '_status', _('Status'));
		o.rawhtml = true;
		o.cfgvalue = function(section_id) {
			var svc = statusData[section_id];
			var health = svc ? svc.health : 'unknown';
			var enabled = svc ? svc.enabled : (uci.get('saturn', section_id, 'enabled') === '1');
			return '<span id="saturn-status-' + section_id + '">' +
				(getStatusBadge(health, enabled)).outerHTML + '</span>';
		};

		o = s.option(form.Value, 'name', _('Name'));
		o.rmempty = false;
		o.placeholder = 'my-service';
		o.validate = function(section_id, value) {
			if (!/^[a-zA-Z0-9_-]+$/.test(value))
				return _('Name must contain only letters, numbers, hyphens and underscores');
			return true;
		};

		o = s.option(form.ListValue, 'deployment', _('Deployment'),
			_('Where the AI service runs.'));
		o.value('cloud', _('Cloud (remote API)'));
		o.value('network', _('Network (local/LAN)'));
		o.rmempty = false;

		o = s.option(form.ListValue, 'api_type', _('API Type'),
			_('The API compatibility format.'));
		o.value('openai', _('OpenAI-compatible'));
		o.value('ollama', _('Ollama-native'));
		o.rmempty = false;

		o = s.option(form.Flag, 'enabled', _('Enabled'));
		o.default = '1';
		o.rmempty = false;

		o = s.option(form.Value, 'priority', _('Priority'),
			_('Lower number = higher priority. Used for client service selection.'));
		o.datatype = 'range(0,100)';
		o.default = '10';
		o.placeholder = '10';

		o = s.option(form.Value, 'base_url', _('Base URL'),
			_('Full base URL of the AI service API (e.g., https://api.openai.com/v1 or http://192.168.1.50:11434).'));
		o.rmempty = false;
		o.placeholder = 'https://api.example.com/v1';
		o.validate = function(section_id, value) {
			if (!value || value.length === 0)
				return _('Base URL is required');
			if (!value.match(/^https?:\/\/.+/))
				return _('Base URL must start with http:// or https://');
			return true;
		};

		o = s.option(form.Value, 'advertise_port', _('Advertise Port'),
			_('Port number for mDNS advertisement. Leave empty for auto-assignment starting at 8400.'));
		o.datatype = 'port';
		o.placeholder = '8400';
		o.depends('deployment', 'cloud');
		o.rmempty = true;

		o = s.option(form.Value, 'api_key', _('API Key'),
			_('Your API key for the service.'));
		o.password = true;
		o.depends('deployment', 'cloud');
		o.rmempty = true;

		o = s.option(form.Value, 'host', _('Host'),
			_('Hostname or IP address where the service is running.'));
		o.datatype = 'host';
		o.placeholder = '192.168.1.50';
		o.depends('deployment', 'network');

		o = s.option(form.Value, 'port', _('Port'),
			_('Port number for the service.'));
		o.datatype = 'port';
		o.depends('deployment', 'network');

		o = s.option(form.Flag, 'ephemeral_keys', _('Ephemeral Keys'),
			_('Enable rotating ephemeral API keys (e.g., for OpenRouter).'));
		o.default = '0';
		o.depends('deployment', 'cloud');

		o = s.option(form.Value, 'key_endpoint', _('Key Generation Endpoint'),
			_('API endpoint for generating ephemeral keys.'));
		o.placeholder = 'https://openrouter.ai/api/v1/keys';
		o.depends('ephemeral_keys', '1');

		o = s.option(form.Value, 'spending_limit', _('Spending Limit'),
			_('USD limit per ephemeral key. Set to 0 for no limit.'));
		o.datatype = 'ufloat';
		o.default = '0';
		o.placeholder = '0';
		o.depends('ephemeral_keys', '1');

		o = s.option(form.Value, 'rotation_interval', _('Rotation Interval'),
			_('Credential rotation interval in seconds.'));
		o.datatype = 'uinteger';
		o.default = '300';
		o.placeholder = '300';
		o.depends('ephemeral_keys', '1');

		o = s.option(form.Value, 'expires_interval', _('Expiration Interval'),
			_('Credential expiration in seconds. Must be greater than rotation interval.'));
		o.datatype = 'uinteger';
		o.default = '600';
		o.placeholder = '600';
		o.depends('ephemeral_keys', '1');

		o.validate = function(section_id, value) {
			var rotation = uci.get('saturn', section_id, 'rotation_interval');
			if (rotation && value) {
				var rot_val = parseInt(rotation, 10);
				var exp_val = parseInt(value, 10);
				if (exp_val <= rot_val) {
					return _('Expiration interval must be greater than rotation interval (%d seconds)').format(rot_val);
				}
			}
			return true;
		};

		o = s.option(form.Value, 'models_filter', _('Models Filter'),
			_('Optional: Comma-separated list of model names to advertise. Leave empty to advertise all models. Example: anthropic/claude-opus-4, openai/gpt-4o, meta-llama/llama-3-70b'));
		o.rmempty = true;
		o.placeholder = 'provider/model-1, provider/model-2';
		o.depends('deployment', 'cloud');

		o = s.option(form.Button, '_test_connection', _('Test Connection'));
		o.inputtitle = _('Test');
		o.inputstyle = 'action';
		o.depends('deployment', 'network');

		o.onclick = function(ev, section_id) {
			var deployment = uci.get('saturn', section_id, 'deployment');
			var api_type = uci.get('saturn', section_id, 'api_type');
			var base_url = uci.get('saturn', section_id, 'base_url');
			var host = uci.get('saturn', section_id, 'host');
			var port = uci.get('saturn', section_id, 'port');
			var api_key = uci.get('saturn', section_id, 'api_key') || '';

			if (!base_url) {
				ui.addNotification(null, E('p', _('Please enter a base URL first.')), 'warning');
				return;
			}

			var btn = ev.target;
			btn.disabled = true;
			btn.value = _('Testing...');

			return callTestConnection(deployment, api_type, base_url, host || '', port || '', api_key).then(function(result) {
				btn.disabled = false;
				btn.value = _('Test');

				if (result.success) {
					ui.addNotification(null, E('p', [
						E('strong', _('Success: ')),
						result.message || _('Connection successful')
					]), 'info');
				} else {
					ui.addNotification(null, E('p', [
						E('strong', _('Failed: ')),
						result.error || _('Connection failed')
					]), 'warning');
				}
			}).catch(function(err) {
				btn.disabled = false;
				btn.value = _('Test');
				ui.addNotification(null, E('p', [
					E('strong', _('Error: ')),
					err.message || _('RPC call failed')
				]), 'error');
			});
		};

		poll.add(updateStatusIndicators, 10);

		return m.render().then(function(mapEl) {
			var sections = mapEl.querySelectorAll('.cbi-section');
			if (sections.length > 0) {
				sections[0].parentNode.insertBefore(serviceControlHtml, sections[0]);
			} else {
				mapEl.insertBefore(serviceControlHtml, mapEl.firstChild);
			}

			var uninstallSection = E('div', { 'class': 'cbi-section', 'style': 'margin-top: 2em; padding-top: 1em; border-top: 1px solid;' }, [
				E('h3', {}, _('Uninstall Saturn')),
				E('p', { 'class': 'saturn-help-text' },
					_('Remove Saturn and all its configuration from this device.')),
				E('button', {
					'class': 'saturn-btn saturn-btn-danger',
					'click': function(ev) {
						if (!confirm(_('This will remove Saturn and all configurations. Continue?'))) {
							return;
						}
						var btn = ev.target;
						btn.disabled = true;
						btn.textContent = _('Uninstalling...');
						
						callUninstall().then(function(result) {
							if (result.success) {
								ui.addNotification(null, E('p', _('Saturn has been uninstalled. Redirecting to home page...')), 'info');
								setTimeout(function() {
									window.location.href = '/cgi-bin/luci/';
								}, 2000);
							} else {
								btn.disabled = false;
								btn.textContent = _('Uninstall Saturn');
								ui.addNotification(null, E('p', [
									E('strong', _('Error: ')),
									result.error || _('Uninstall failed')
								]), 'error');
							}
						}).catch(function(err) {
							btn.disabled = false;
							btn.textContent = _('Uninstall Saturn');
							ui.addNotification(null, E('p', [
								E('strong', _('Error: ')),
								err.message || _('RPC call failed')
							]), 'error');
						});
					}
				}, _('Uninstall Saturn'))
			]);
			
			mapEl.appendChild(uninstallSection);
			return mapEl;
		});
	}
});
