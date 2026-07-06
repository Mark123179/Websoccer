<?php
/**
 * System-Diagnose — zentrale Übersicht (Jobs, Simulation, Logs, Liveticker, Sponsoren).
 * Admin → ?site=system-diagnostics
 */

if (!$admin['r_admin'] && !$admin['r_demo']) {
	echo '<p>' . getMessage('error_access_denied') . '</p>';
	exit;
}

include CONFIGCACHE_SETTINGS;

$clubId = isset($_REQUEST['club_id']) ? (int) $_REQUEST['club_id'] : 0;
$livetickerLimit = isset($_REQUEST['lt_limit']) ? (int) $_REQUEST['lt_limit'] : 100;

if (!class_exists('SystemDiagnosticsService', false)) {
	require_once BASE_FOLDER . '/classes/services/SystemDiagnosticsService.class.php';
}

$ws = (isset($website) && $website instanceof WebSoccer) ? $website : WebSoccer::getInstance();
$report = SystemDiagnosticsService::runFullReport($ws, $db, array(
	'club_id' => $clubId,
	'liveticker_limit' => $livetickerLimit,
));
$summary = $report['summary'];
$sections = $report['sections'];

$title = hasMessage('system_diagnostics_title') ? getMessage('system_diagnostics_title') : 'System-Diagnose';
$intro = hasMessage('system_diagnostics_intro')
	? getMessage('system_diagnostics_intro')
	: 'Prüft Kernfeatures, Klassen, Tabellen, Spalten, Adminseiten, Jobs, Logs, Simulation, Liveticker und Sponsoren.';
echo '<h1>' . escapeOutput($title) . '</h1>';
echo '<p class="muted">' . escapeOutput($intro) . '</p>';

echo '<div class="row" style="margin-bottom:16px;">';
$summaryLabels = array(
	'error' => 'Fehler / läuft nicht',
	'warn' => 'Prüfen / anpassen',
	'ok' => 'OK',
	'info' => 'Info',
);
foreach (array('error' => 'danger', 'warn' => 'warning', 'ok' => 'success', 'info' => 'info') as $key => $cls) {
	$c = (int) ($summary[$key] ?? 0);
	echo '<div class="col-md-3 col-sm-6" style="margin-bottom:8px;">';
	echo '<div class="alert alert-' . $cls . '" style="margin:0;text-align:center;">';
	echo '<strong style="font-size:22px;">' . $c . '</strong><br>' . escapeOutput($summaryLabels[$key]);
	echo '</div></div>';
}
echo '</div>';

echo '<form method="get" class="form-inline well" style="margin-bottom:16px;">';
echo '<input type="hidden" name="site" value="' . escapeOutput($site) . '">';
echo '<label>Verein-ID (Sponsor-Detail) </label>';
echo '<input type="number" name="club_id" value="' . (int) $clubId . '" min="0" class="input-small" style="width:90px;margin:0 8px;">';
echo '<label>Liveticker-Spiele </label>';
echo '<input type="number" name="lt_limit" value="' . (int) $livetickerLimit . '" min="10" max="500" class="input-small" style="width:70px;margin:0 8px;">';
echo '<button type="submit" class="btn btn-primary">Prüfung aktualisieren</button>';
echo ' <a class="btn btn-default" href="index.php?site=simulationtest">Simulation Test</a>';
echo '</form>';

$levelClass = array(
	'error' => 'danger',
	'warn' => 'warning',
	'ok' => 'success',
	'info' => 'info',
);

foreach ($sections as $sec) {
	$sev = (string) ($sec['severity'] ?? 'info');
	$panelCls = isset($levelClass[$sev]) ? $levelClass[$sev] : 'default';
	echo '<div class="panel panel-' . escapeOutput($panelCls) . '" style="margin-bottom:12px;">';
	echo '<div class="panel-heading"><strong>' . escapeOutput((string) ($sec['title'] ?? '')) . '</strong></div>';
	echo '<div class="panel-body" style="padding:0;">';
	echo '<table class="table table-condensed" style="margin:0;background:#fff;">';
	echo '<thead><tr><th style="width:90px;">Status</th><th style="width:220px;">Thema</th><th>Details</th></tr></thead><tbody>';
	foreach ((array) ($sec['items'] ?? array()) as $item) {
		$lvl = (string) ($item['level'] ?? 'info');
		$badge = isset($levelClass[$lvl]) ? $levelClass[$lvl] : 'default';
		echo '<tr>';
		echo '<td><span class="label label-' . escapeOutput($badge) . '">' . escapeOutput(strtoupper($lvl)) . '</span></td>';
		echo '<td>' . escapeOutput((string) ($item['title'] ?? '')) . '</td>';
		echo '<td><pre style="margin:0;white-space:pre-wrap;font-size:12px;border:0;background:transparent;">'
			. escapeOutput((string) ($item['detail'] ?? '')) . '</pre></td>';
		echo '</tr>';
	}
	echo '</tbody></table></div></div>';
}

echo '<div class="alert alert-info">';
echo '<strong>' . escapeOutput(getMessage('system_diagnostics_limits_title')) . '</strong><br>';
echo escapeOutput(getMessage('system_diagnostics_limits_body'));
echo '</div>';
