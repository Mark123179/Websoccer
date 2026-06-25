<?php
/**
 * Simulation Test – quick diagnostics and recommended defaults.
 * Access: Admin -> ?site=simulationtest
 */

if (!$admin['r_admin'] && !$admin['r_demo']) {
	echo '<p>' . getMessage('error_access_denied') . '</p>';
	exit;
}

include CONFIGCACHE_SETTINGS;

if (class_exists('SimulationStateHelper') && isset($db) && is_object($db)) {
	try {
		SimulationStateHelper::ensureMatchAggregateSchema($db);
		if (method_exists('SimulationStateHelper', 'ensureLiveMatchTacticSchema')) {
			SimulationStateHelper::ensureLiveMatchTacticSchema($db);
		}
		SimulationStateHelper::ensureExtendedStatsSchema($db);
	} catch (Throwable $e) {
		// Statistik-Block fällt ggf. zurück; keine harte Abhängigkeit
	}
}

if (!class_exists('MatchWeatherService', false) && file_exists(BASE_FOLDER . '/classes/services/MatchWeatherService.class.php')) {
	require_once BASE_FOLDER . '/classes/services/MatchWeatherService.class.php';
}
if (class_exists('MatchWeatherService') && isset($db) && is_object($db)) {
	try {
		MatchWeatherService::ensureSchema($db);
	} catch (Throwable $e) {
		// Wetter-Diagnose fällt ggf. zurück; keine harte Abhängigkeit
	}
}

/** @var array<string,int> Kernparameter (gleiche Logik wie in modules/simulation/module.xml Defaults) */
$recommended = array(
	'sim_goaly_influence' => 25,
	'sim_shootprobability' => 90,
	'sim_cardsprobability' => 90,
	'sim_injuredprobability' => 84,
	'sim_weight_strength' => 32,
	'sim_weight_strengthTech' => 26,
	'sim_weight_strengthStamina' => 18,
	'sim_weight_strengthFreshness' => 12,
	'sim_weight_strengthSatisfaction' => 12,
	'sim_home_field_advantage' => 2,
	'sim_weather_impact_global_pct' => 108,
	'sim_weather_pass_effect_pct' => 115,
	'sim_weather_shoot_effect_pct' => 108,
	'sim_weather_dribble_effect_pct' => 108,
	'sim_weather_injury_effect_pct' => 104,
	'sim_weather_wind_effect_pct' => 106,
	'sim_weather_heat_fatigue_pct' => 106,
);

/** @var array<string,int> Ambient-Minute & Eckbälle (DefaultSimulationStrategy) */
$recommendedAmbientCorners = array(
	'sim_ambient_pulse_min' => 2,
	'sim_ambient_pulse_max' => 4,
	'sim_ambient_pulse_cap' => 7,
	'sim_ambient_pulse_offensive_thresh' => 64,
	'sim_ambient_pulse_press_sum' => 5,
	'sim_ambient_branch_1' => 30,
	'sim_ambient_branch_2' => 47,
	'sim_ambient_branch_3' => 84,
	'sim_ambient_branch_4' => 90,
	'sim_corner_miss_base' => 9,
	'sim_corner_miss_strength_per' => 18,
	'sim_corner_miss_cap' => 40,
	'sim_corner_miss_wings' => 3,
	'sim_corner_miss_longpass' => 2,
	'sim_corner_miss_weather' => 2,
	'sim_corner_after_miss_min_p' => 5,
	'sim_corner_after_miss_max_p' => 46,
	'sim_corner_silent_weight_base' => 31,
	'sim_corner_silent_wings_bonus' => 5,
	'sim_corner_silent_longpass_def_mod' => -5,
	'sim_corner_silent_roll_cap' => 70,
);

/** @var array<string,int> Experten / Job-Lauf (Kategorie simulation_expert in module.xml) */
$recommendedRuntime = array(
	'sim_interval' => 7,
	'sim_max_matches_per_run' => 60,
	'sim_batch_cap_enabled' => 0,
	'sim_batch_max_minutes_per_match' => 15,
	'sim_skip_kickoff_delay' => 1,
);

$queueFlash = null;

if (isset($show) && $show === 'release_queue' && isset($db) && is_object($db)) {
	if ($admin['r_demo']) {
		$queueFlash = array('type' => 'danger', 'text' => getMessage('validationerror_no_changes_as_demo'));
	} else {
		if (!class_exists('MatchSimulationExecutor', false)) {
			require_once BASE_FOLDER . '/classes/MatchSimulationExecutor.class.php';
		}
		$released = MatchSimulationExecutor::releaseStaleBlockedMatches($db, 90);
		$queueFlash = array(
			'type' => 'success',
			'text' => 'Queue freigegeben: ' . (int) $released . ' Spiel(e) von blocked=1 befreit. Der Cron kann sie beim nächsten Lauf wieder aufnehmen.',
		);
	}
}

if (isset($show) && $show === 'force_match' && isset($db) && is_object($db)) {
	if ($admin['r_demo']) {
		$queueFlash = array('type' => 'danger', 'text' => getMessage('validationerror_no_changes_as_demo'));
	} else {
		if (!class_exists('MatchSimulationExecutor', false)) {
			require_once BASE_FOLDER . '/classes/MatchSimulationExecutor.class.php';
		}
		$ws = (isset($website) && $website instanceof WebSoccer) ? $website : WebSoccer::getInstance();
		$matchIdForce = (int) ($_REQUEST['match_id'] ?? 0);
		@set_time_limit(0);
		$result = MatchSimulationExecutor::forceSimulateMatchById($ws, $db, $matchIdForce);
		$msg = 'Spiel #' . $matchIdForce . ': Minuten=' . (int) $result['minutes']
			. ', berechnet=' . escapeOutput((string) $result['berechnet']);
		if (strlen((string) $result['error'])) {
			$msg .= ' — Fehler: ' . $result['error'];
		}
		$queueFlash = array(
			'type' => !empty($result['ok']) ? 'success' : 'danger',
			'text' => $msg,
		);
	}
}

if (isset($show) && $show === 'catchup' && isset($db) && is_object($db)) {
	if ($admin['r_demo']) {
		$queueFlash = array('type' => 'danger', 'text' => getMessage('validationerror_no_changes_as_demo'));
	} else {
		if (!class_exists('MatchSimulationExecutor', false)) {
			require_once BASE_FOLDER . '/classes/MatchSimulationExecutor.class.php';
		}
		$ws = (isset($website) && $website instanceof WebSoccer) ? $website : WebSoccer::getInstance();
		$runs = isset($_REQUEST['runs']) ? (int) $_REQUEST['runs'] : 15;
		@set_time_limit(0);
		$result = MatchSimulationExecutor::simulateCatchupRuns($ws, $db, $runs);
		$queueFlash = array(
			'type' => ((int) $result['open_remaining'] > 0) ? 'warning' : 'success',
			'text' => 'Nachhol-Simulation: ' . (int) $result['runs'] . ' Lauf/Läufe, '
				. (int) $result['released_blocked'] . ' Sperre(n) gelöst, '
				. (int) $result['open_remaining'] . ' offene fällige Spiele verbleiben.',
		);
	}
}

if (isset($show) && $show === 'apply') {
	if ($admin['r_demo']) {
		$err[] = getMessage('validationerror_no_changes_as_demo');
	}
	if (isset($err)) {
		include('validationerror.inc.php');
	} else {
		$newSettings = array();
		foreach ($setting as $settingId => $settingData) {
			$newSettings[$settingId] = (string) getConfig($settingId);
		}
		foreach ($recommended as $key => $val) {
			$newSettings[$key] = (string) $val;
		}
		foreach ($recommendedAmbientCorners as $key => $val) {
			$newSettings[$key] = (string) $val;
		}
		foreach ($recommendedRuntime as $key => $val) {
			$newSettings[$key] = (string) $val;
		}
		$cf = ConfigFileWriter::getInstance($conf);
		$cf->saveSettings($newSettings);
		echo createSuccessMessage(getMessage('alert_save_success'), 'Empfohlene Simulationswerte (Kern + Ambient/Ecken + Laufzeit) wurden gesetzt.');
		echo createWarningMessage(getMessage('settings_saved_note_restartjobs'), getMessage('settings_saved_note_restartjobs_details'));
	}
}

if (!function_exists('simtest_has_column')) {
	function simtest_has_column($db, $table, $column) {
		if (!isset($db) || !is_object($db) || !isset($db->connection) || !($db->connection instanceof mysqli)) {
			return false;
		}
		$table = preg_replace('/[^a-zA-Z0-9_]/', '', (string) $table);
		$columnEsc = $db->connection->real_escape_string((string) $column);
		$res = @$db->connection->query("SHOW COLUMNS FROM `" . $table . "` LIKE '" . $columnEsc . "'");
		$ok = $res && (int) $res->num_rows > 0;
		if ($res) {
			$res->free();
		}
		return $ok;
	}
}

if (!function_exists('simtest_existing_columns')) {
	function simtest_existing_columns($db, $table, array $columns) {
		$count = 0;
		foreach ($columns as $column) {
			if (simtest_has_column($db, $table, $column)) {
				$count++;
			}
		}
		return $count;
	}
}

if (!function_exists('simtest_scalar')) {
	function simtest_scalar($db, $sql, $default = 0) {
		if (!isset($db) || !is_object($db) || !isset($db->connection) || !($db->connection instanceof mysqli)) {
			return $default;
		}
		$res = @$db->connection->query($sql);
		if (!$res) {
			return $default;
		}
		$row = $res->fetch_array(MYSQLI_NUM);
		$res->free();
		if (!$row || !isset($row[0])) {
			return $default;
		}
		return $row[0];
	}
}

if (!function_exists('simtest_class_file_available')) {
	function simtest_class_file_available($className) {
		$path = BASE_FOLDER . '/classes/' . $className . '.class.php';
		if (file_exists($path)) {
			return true;
		}
		$servicePath = BASE_FOLDER . '/classes/services/' . $className . '.class.php';
		return file_exists($servicePath);
	}
}

if (!function_exists('simtest_status_badge')) {
	function simtest_status_badge($status) {
		$status = (string) $status;
		$label = 'Prüfen';
		$cls = 'label label-warning';
		if ($status === 'ok') {
			$label = 'OK';
			$cls = 'label label-success';
		} elseif ($status === 'warn') {
			$label = 'Teilweise';
			$cls = 'label label-warning';
		} elseif ($status === 'bad') {
			$label = 'Fehlt';
			$cls = 'label label-important';
		} elseif ($status === 'info') {
			$label = 'Info';
			$cls = 'label label-info';
		}
		return '<span class="' . $cls . '">' . escapeOutput($label) . '</span>';
	}
}

if (!function_exists('simtest_add_feature_row')) {
	function simtest_add_feature_row(array &$rows, $name, $status, $works, $evidence, $risk, $recommendation) {
		$rows[] = array(
			'name' => (string) $name,
			'status' => (string) $status,
			'works' => (string) $works,
			'evidence' => (string) $evidence,
			'risk' => (string) $risk,
			'recommendation' => (string) $recommendation,
		);
	}
}

echo '<h1>Simulation Test</h1>';
echo '<p class="muted">Ist-Zustand vs. empfohlene Werte für die Match-Simulation (global). Entspricht den Standard-Defaults in <code>modules/simulation/module.xml</code>, soweit unten aufgeführt. Ambient &amp; Eckbälle steuern in <code>DefaultSimulationStrategy</code> die stille Hintergrundaktivität und die Eckball-Häufigkeit.</p>';

if (is_array($queueFlash) && isset($queueFlash['type'], $queueFlash['text'])) {
	$cls = 'alert-info';
	if ($queueFlash['type'] === 'success') {
		$cls = 'alert-success';
	} elseif ($queueFlash['type'] === 'warning') {
		$cls = 'alert-warning';
	} elseif ($queueFlash['type'] === 'danger') {
		$cls = 'alert-danger';
	}
	echo '<div class="alert ' . escapeOutput($cls) . '">' . escapeOutput($queueFlash['text']) . '</div>';
}

echo '<div class="alert alert-info" style="margin-bottom:16px;">';
echo '<strong>Simulationsintervall</strong> (<code>sim_interval</code>): ';
echo 'Anzahl Minuten, die <em>pro Job-Ausführung</em> nacheinander berechnet werden. ';
echo '<strong>150</strong> ≈ volles Spiel in einem Lauf (schnelles Endergebnis, weniger Wartezeit durch Cron). ';
echo 'Kleine Werte (z. B. <strong>2</strong>) erzeugen feinere „Live“-Schritte, aber mehr Durchläufe bis zum Abpfiff.';
echo '</div>';

echo '<form action="' . $_SERVER['PHP_SELF'] . '" method="post" class="form-horizontal" style="margin-bottom:16px;">';
echo '<input type="hidden" name="site" value="' . escapeOutput($site) . '">';
echo '<input type="hidden" name="show" value="apply">';
echo '<button type="submit" class="btn btn-primary">Empfohlene Werte übernehmen (Kern + Ambient/Ecken + Laufzeit)</button>';
echo '</form>';

echo '<h2>Kernparameter</h2>';
echo '<table class="table table-striped table-bordered">';
echo '<thead><tr><th>Setting</th><th>Aktuell</th><th>Empfohlen</th><th>Status</th></tr></thead><tbody>';

$ok = 0;
$warn = 0;
foreach ($recommended as $key => $target) {
	$current = (int) getConfig($key, (string) $target);
	$delta = abs($current - (int) $target);
	$status = 'OK';
	$class = 'text-success';
	if ($delta >= 8) {
		$status = 'Abweichung hoch';
		$class = 'text-danger';
		$warn++;
	} elseif ($delta >= 3) {
		$status = 'Abweichung mittel';
		$class = 'text-warning';
		$warn++;
	} else {
		$ok++;
	}
	echo '<tr>';
	echo '<td><code>' . escapeOutput($key) . '</code></td>';
	echo '<td>' . (int) $current . '</td>';
	echo '<td>' . (int) $target . '</td>';
	echo '<td class="' . $class . '">' . escapeOutput($status) . '</td>';
	echo '</tr>';
}
echo '</tbody></table>';

echo '<h2>Ambient-Minute &amp; Eckbälle</h2>';
echo '<p class="muted small">Pulse: zusätzliche stille Events pro Spielminute. <code>sim_ambient_branch_*</code>: Schwellen 1–100 (Würfel) für impliziten Pass, Ballverlust, Micro-Duell, stille Standards, Pressing — müssen aufsteigend sein (wird intern begrenzt). Eckbälle: nach Fehlschuss und bei stillen Standards.</p>';
echo '<table class="table table-striped table-bordered">';
echo '<thead><tr><th>Setting</th><th>Aktuell</th><th>Empfohlen</th><th>Status</th></tr></thead><tbody>';

foreach ($recommendedAmbientCorners as $key => $target) {
	$current = (int) getConfig($key, (string) $target);
	$delta = abs($current - (int) $target);
	$status = 'OK';
	$class = 'text-success';
	if ($delta >= 8) {
		$status = 'Abweichung hoch';
		$class = 'text-danger';
		$warn++;
	} elseif ($delta >= 3) {
		$status = 'Abweichung mittel';
		$class = 'text-warning';
		$warn++;
	} else {
		$ok++;
	}
	echo '<tr>';
	echo '<td><code>' . escapeOutput($key) . '</code></td>';
	echo '<td>' . (int) $current . '</td>';
	echo '<td>' . (int) $target . '</td>';
	echo '<td class="' . $class . '">' . escapeOutput($status) . '</td>';
	echo '</tr>';
}
echo '</tbody></table>';

if (isset($db) && is_object($db)) {
	$nowDiag = getNowAsTimestamp();
	$openDue = 0;
	$blockedDue = 0;
	$stuckKickoff = 0;
	try {
		$r1 = $db->querySelect('COUNT(*) AS hits', 'spiel', "berechnet != '1' AND blocked != '1' AND datum <= %d", $nowDiag, 1);
		$row1 = $r1 ? $r1->fetch_array() : null;
		if ($r1) {
			$r1->free();
		}
		$openDue = (int) ($row1['hits'] ?? 0);
		$r2 = $db->querySelect('COUNT(*) AS hits', 'spiel', "berechnet != '1' AND blocked = '1' AND datum <= %d", $nowDiag, 1);
		$row2 = $r2 ? $r2->fetch_array() : null;
		if ($r2) {
			$r2->free();
		}
		$blockedDue = (int) ($row2['hits'] ?? 0);
		$r3 = $db->querySelect('COUNT(*) AS hits', 'spiel', "berechnet != '1' AND (minutes IS NULL OR minutes = 0) AND datum <= %d AND datum >= %d", array($nowDiag, $nowDiag - 3600), 1);
		$row3 = $r3 ? $r3->fetch_array() : null;
		if ($r3) {
			$r3->free();
		}
		$stuckKickoff = (int) ($row3['hits'] ?? 0);
	} catch (Throwable $e) {
		// ignore
	}
	echo '<div class="alert alert-warning" style="margin-bottom:16px;">';
	echo '<strong>Spiel-Queue (jetzt)</strong><br>';
	echo 'Fällig &amp; simulierbar: <strong>' . $openDue . '</strong> · ';
	echo 'Fällig aber <code>blocked=1</code> (hängen oft auf „LIVE / Anpfiff“): <strong>' . $blockedDue . '</strong> · ';
	echo 'Anpfiff 0\' (letzte Stunde): <strong>' . $stuckKickoff . '</strong><br>';
	echo '<p style="margin:10px 0 0;">Kein manuelles SQL nötig — der Cron löst <code>blocked</code> automatisch; bei Rückstand greift der Nachhol-Modus.</p>';
	echo '<form action="' . escapeOutput($_SERVER['PHP_SELF']) . '" method="get" class="form-inline" style="margin-top:8px;">';
	echo '<input type="hidden" name="site" value="' . escapeOutput($site) . '">';
	echo '<button type="submit" name="show" value="release_queue" class="btn btn-warning btn-sm">Queue freigeben (blocked=0)</button> ';
	echo '<button type="submit" name="show" value="catchup" class="btn btn-primary btn-sm">Offene Spiele nachholen (15 Läufe)</button>';
	echo '</form>';
	echo '<form action="' . escapeOutput($_SERVER['PHP_SELF']) . '" method="get" class="form-inline" style="margin-top:8px;">';
	echo '<input type="hidden" name="site" value="' . escapeOutput($site) . '">';
	echo '<label>Einzelspiel erzwingen ID </label>';
	echo '<input type="number" name="match_id" value="1927" min="1" class="input-small" style="width:90px;margin:0 6px;">';
	echo '<button type="submit" name="show" value="force_match" class="btn btn-danger btn-sm">Jetzt simulieren (zeigt Fehler)</button>';
	echo '</form>';
	if ($openDue > 0 || $blockedDue > 0) {
		try {
			$listSql = 'SELECT id, spieltyp, datum, minutes, blocked, home_verein, gast_verein FROM spiel'
				. " WHERE berechnet != '1' AND datum <= " . (int) $nowDiag
				. ' ORDER BY datum ASC, id ASC LIMIT 25';
			$listRes = @$db->connection->query($listSql);
			if ($listRes && $listRes->num_rows > 0) {
				echo '<table class="table table-condensed" style="margin-top:10px;background:#fff;"><thead><tr>'
					. '<th>ID</th><th>Typ</th><th>Anpfiff</th><th>Min.</th><th>blocked</th><th>Teams</th></tr></thead><tbody>';
				while ($lm = $listRes->fetch_assoc()) {
					echo '<tr><td>' . (int) ($lm['id'] ?? 0) . '</td>';
					echo '<td>' . escapeOutput((string) ($lm['spieltyp'] ?? '')) . '</td>';
					echo '<td>' . escapeOutput(date('d.m.Y H:i', (int) ($lm['datum'] ?? 0))) . '</td>';
					echo '<td>' . (int) ($lm['minutes'] ?? 0) . '</td>';
					echo '<td>' . escapeOutput((string) ($lm['blocked'] ?? '')) . '</td>';
					echo '<td>' . (int) ($lm['home_verein'] ?? 0) . ' : ' . (int) ($lm['gast_verein'] ?? 0) . '</td></tr>';
				}
				echo '</tbody></table>';
				$listRes->free();
			}
		} catch (Throwable $e) {
			// ignore list errors
		}
	}
	echo '</div>';
}

echo '<h2>Laufzeit / Job (simulation_expert)</h2>';
echo '<table class="table table-striped table-bordered">';
echo '<thead><tr><th>Setting</th><th>Aktuell</th><th>Empfohlen</th><th>Status</th></tr></thead><tbody>';

foreach ($recommendedRuntime as $key => $target) {
	$current = (int) getConfig($key, (string) $target);
	$status = 'OK';
	$class = 'text-success';

	if ($key === 'sim_interval') {
		if ($current >= 90) {
			$ok++;
			$status = 'OK (großer Batch)';
		} elseif ($current >= 31) {
			$warn++;
			$status = 'Mittlere Batches';
			$class = 'text-warning';
		} else {
			$warn++;
			$status = 'Kleine Schritte (viele Job-Runden)';
			$class = 'text-warning';
		}
	} else {
		$delta = abs($current - (int) $target);
		if ($delta >= 8) {
			$status = 'Abweichung hoch';
			$class = 'text-danger';
			$warn++;
		} elseif ($delta >= 3) {
			$status = 'Abweichung mittel';
			$class = 'text-warning';
			$warn++;
		} else {
			$ok++;
		}
	}

	echo '<tr>';
	echo '<td><code>' . escapeOutput($key) . '</code></td>';
	echo '<td>' . (int) $current . '</td>';
	echo '<td>' . (int) $target . '</td>';
	echo '<td class="' . $class . '">' . escapeOutput($status) . '</td>';
	echo '</tr>';
}
echo '</tbody></table>';

echo '<h2>Letzte Spiele (Statistik)</h2>';
echo '<p class="muted small">Mittelwerte aus den letzten 50 abgeschlossenen Spielen (<code>spiel.berechnet = 1</code>). Nur zur Orientierung — keine automatische Bewertung.</p>';
$statsDone = false;
if (isset($db) && is_object($db) && isset($db->connection) && $db->connection instanceof mysqli) {
	$sampleN = 50;
	$sql = 'SELECT AVG(hc) AS ah, AVG(gc) AS ag, AVG(ht + gt) AS goals, COUNT(*) AS n FROM ('
		. 'SELECT home_corners AS hc, gast_corners AS gc, home_tore AS ht, gast_tore AS gt FROM spiel WHERE berechnet = \'1\' ORDER BY datum DESC LIMIT ' . (int) $sampleN
		. ') t';
	$res = @$db->connection->query($sql);
	if ($res && ($row = $res->fetch_assoc())) {
		$statsDone = true;
		$n = (int) ($row['n'] ?? 0);
		$ah = isset($row['ah']) ? round((float) $row['ah'], 2) : 0;
		$ag = isset($row['ag']) ? round((float) $row['ag'], 2) : 0;
		$goals = isset($row['goals']) ? round((float) $row['goals'], 2) : 0;
		echo '<table class="table table-bordered" style="max-width:520px;"><tbody>';
		echo '<tr><td>Anzahl Spiele</td><td>' . (int) $n . '</td></tr>';
		echo '<tr><td>Ø Ecken Heim</td><td>' . escapeOutput((string) $ah) . '</td></tr>';
		echo '<tr><td>Ø Ecken Gast</td><td>' . escapeOutput((string) $ag) . '</td></tr>';
		echo '<tr><td>Ø Tore pro Spiel (gesamt)</td><td>' . escapeOutput((string) $goals) . '</td></tr>';
		echo '</tbody></table>';
		if ($n > 0 && ($ah > 15 || $ag > 15)) {
			echo '<div class="alert alert-warning" style="margin-top:16px;">';
			echo 'Hinweis: Ø Ecken über 15 pro Team deuten oft auf zu hohe Einstellungen (z. B. <code>sim_ambient_branch_*</code>, <code>sim_corner_silent_*</code>, <code>sim_corner_miss_*</code>). ';
			echo '</div>';
		}
		$res->free();
	}
}
if (!$statsDone) {
	echo '<p class="text-muted">Keine Statistik verfügbar (Datenbank oder Spalten).</p>';
}

echo '<h2>Feature-Analyse Spielberechnung</h2>';
echo '<p class="muted small">Ampel zur Frage: Ist das Feature im Code vorhanden, sind die nötigen Daten/Spalten da und sieht man in den letzten berechneten Spielen bereits messbare Nutzung? Details stehen in den Tabellen darunter.</p>';

$featureRows = array();
$featureOk = 0;
$featureWarn = 0;
$featureBad = 0;

if (isset($db) && is_object($db) && isset($db->connection) && $db->connection instanceof mysqli) {
	$paColumns = array('pa_1','pa_2','pa_3','pa_4','pa_5','pa_6','pa_7','pa_8');
	$paExisting = simtest_existing_columns($db, 'spieler', $paColumns);
	$paInStats = simtest_has_column($db, 'spiel_berechnung', 'position_main');
	$paPlayers = ($paExisting === 8)
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spieler WHERE COALESCE(pa_1,'') != '' AND COALESCE(pa_2,'') != '' AND COALESCE(pa_3,'') != '' AND COALESCE(pa_4,'') != '' AND COALESCE(pa_5,'') != '' AND COALESCE(pa_6,'') != '' AND COALESCE(pa_7,'') != '' AND COALESCE(pa_8,'') != ''", 0)
		: 0;
	$paRecentPositions = $paInStats
		? (int) simtest_scalar($db, "SELECT COUNT(DISTINCT position_main) FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id WHERE S.berechnet = '1' AND COALESCE(position_main,'') != ''", 0)
		: 0;
	$paStatus = (simtest_class_file_available('PlayerAttributeDefinitionService') && simtest_class_file_available('PlayerAttributeSimulationBridge') && $paExisting === 8 && $paPlayers > 0 && $paRecentPositions >= 6) ? 'ok' : 'warn';
	if ($paExisting < 8 || !simtest_class_file_available('PlayerAttributeDefinitionService')) {
		$paStatus = 'bad';
	}
	simtest_add_feature_row($featureRows, 'Positionsspezifische Attribute',
		$paStatus,
		'Positionsslots pa_1 bis pa_8 werden geladen und in Zweikämpfen sowie Positionsauswertung berücksichtigt.',
		'Spieler mit vollständigen PA-Slots: ' . $paPlayers . ' | Spalten: ' . $paExisting . '/8 | Positionen in Statistik: ' . $paRecentPositions,
		($paPlayers < 1 ? 'Alte/fehlende Spielerattribute führen zu Fallbackwerten und schwächen Positionslogik.' : 'Wirkung ist vorhanden; Zielmatrix unten zeigt, ob Rollen realistisch auseinanderlaufen.'),
		'Nach größeren Imports einmal Attribut-/Kopfball-Sync ausführen und die Positions-Zielmatrix beobachten.'
	);

	$psExisting = simtest_existing_columns($db, 'spieler', array('ps_1','ps_2','ps_3'));
	$playstyleEnabled = ((int) getConfig('playstyle_enabled', '1') === 1);
	$stylePlayers = ($psExisting === 3)
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spieler WHERE COALESCE(ps_1,'') != '' OR COALESCE(ps_2,'') != '' OR COALESCE(ps_3,'') != ''", 0)
		: 0;
	$styleRecent = ($psExisting === 3)
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id INNER JOIN spieler P ON P.id = SB.spieler_id WHERE S.berechnet = '1' AND (COALESCE(P.ps_1,'') != '' OR COALESCE(P.ps_2,'') != '' OR COALESCE(P.ps_3,'') != '')", 0)
		: 0;
	$styleStatus = (simtest_class_file_available('PlayerPlayingStyleService') && simtest_class_file_available('PlayerPlaystyleCatalog') && $playstyleEnabled && $psExisting === 3 && $stylePlayers > 0) ? 'ok' : 'warn';
	if ($psExisting < 3 || !simtest_class_file_available('PlayerPlayingStyleService')) {
		$styleStatus = 'bad';
	}
	simtest_add_feature_row($featureRows, 'Spielerstile / PlayerPlaystyles',
		$styleStatus,
		'Bei passenden Aktionen fragt die Engine den Stilkontext ab und vergibt konfigurierbare Erfolgsboni.',
		'Setting aktiv: ' . ($playstyleEnabled ? 'ja' : 'nein') . ' | Spieler mit Stil: ' . $stylePlayers . ' | Style-Einsätze in berechneten Spielen: ' . $styleRecent,
		(!$playstyleEnabled ? 'Feature ist per Setting deaktiviert.' : ($stylePlayers < 1 ? 'Ohne zugewiesene Stile gibt es keine messbare Wirkung.' : 'Schnellcheck unten zeigt, ob Stilgruppen statistisch über-/unterperformen.')),
		'Wenn die Werte unten neutral bleiben: Bonus-Cap leicht erhöhen oder Stilzuweisung bei Spielern prüfen.'
	);

	$heightCol = simtest_has_column($db, 'spieler', 'groesse');
	$heightPlayers = $heightCol ? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spieler WHERE groesse BETWEEN 150 AND 220", 0) : 0;
	$tallAerialPlayers = $heightCol
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spieler WHERE groesse >= 185 AND COALESCE(position_main,'') IN ('IV','MS','LS','RS','ST')", 0)
		: 0;
	$headerService = simtest_class_file_available('KopfballStaerkeService');
	$headerStatus = ($headerService && $heightCol && $heightPlayers > 0) ? 'ok' : 'bad';
	simtest_add_feature_row($featureRows, 'Kopfballstärke',
		$headerStatus,
		'Fester Wert aus Körpergröße und Position; IV und zentrale Stürmer profitieren stärker als Flügel.',
		'Größenwerte 150-220 cm: ' . $heightPlayers . ' | große IV/ST: ' . $tallAerialPlayers . ' | Service: ' . ($headerService ? 'vorhanden' : 'fehlt'),
		(!$heightCol ? 'Ohne groesse-Spalte kann kein realistischer fixer Kopfballwert entstehen.' : 'Wirkung greift besonders bei Ecken, Flanken und hohen Klärungen.'),
		'Bei auffällig wenig Kopfballtoren: Eckball-/Flanken-Ticker unten und Zielmatrix ST/IV prüfen.'
	);

	$weatherCols = simtest_existing_columns($db, 'spiel', array('weather_type','weather_temp','weather_wind','weather_season','weather_live_done'));
	$weatherEnabled = ((int) getConfig('sim_weather_enabled', '1') === 1);
	$weatherGames = ($weatherCols >= 1)
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spiel WHERE berechnet = '1' AND COALESCE(weather_type,'') != ''", 0)
		: 0;
	$rainGames = ($weatherCols >= 1)
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spiel WHERE berechnet = '1' AND weather_type = 'rain'", 0)
		: 0;
	$weatherStatus = (simtest_class_file_available('MatchWeatherService') && $weatherCols === 5 && $weatherEnabled && $weatherGames > 0) ? 'ok' : 'warn';
	if (!simtest_class_file_available('MatchWeatherService') || $weatherCols < 5) {
		$weatherStatus = 'bad';
	}
	simtest_add_feature_row($featureRows, 'Wetter-System',
		$weatherStatus,
		'Wetter wird vor dem Spiel gesetzt, kann live wechseln und wirkt auf Pässe, Schüsse, Keeper und hohe Bälle.',
		'Spalten: ' . $weatherCols . '/5 | Setting aktiv: ' . ($weatherEnabled ? 'ja' : 'nein') . ' | berechnete Spiele mit Wetter: ' . $weatherGames . ' | Regen: ' . $rainGames,
		($weatherGames < 1 ? 'Noch keine berechneten Spiele mit Wetterdaten oder Schema nicht initialisiert.' : 'Regenanteil und Wettertexte sollten im Liveticker sichtbar sein.'),
		'Wenn Regen nie erscheint: Länder-Wetterprofile oder sim_weather_enabled prüfen.'
	);

	$tacticCols = array('home_tactic_def','home_tactic_mid','home_tactic_att','home_press_def','home_press_mid','home_press_att','gast_tactic_def','gast_tactic_mid','gast_tactic_att','gast_press_def','gast_press_mid','gast_press_att');
	$tacticExisting = simtest_existing_columns($db, 'spiel', $tacticCols);
	$tacticGames = ($tacticExisting === count($tacticCols))
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spiel WHERE berechnet = '1' AND COALESCE(home_tactic_def,'') != '' AND COALESCE(gast_tactic_def,'') != ''", 0)
		: 0;
	$strongPressGames = ($tacticExisting === count($tacticCols))
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spiel WHERE berechnet = '1' AND ((COALESCE(home_press_def,1)+COALESCE(home_press_mid,1)+COALESCE(home_press_att,1)) >= 5 OR (COALESCE(gast_press_def,1)+COALESCE(gast_press_mid,1)+COALESCE(gast_press_att,1)) >= 5)", 0)
		: 0;
	$tacticStatus = (simtest_class_file_available('TacticalSystemService') && $tacticExisting === count($tacticCols) && $tacticGames > 0) ? 'ok' : 'warn';
	if (!simtest_class_file_available('TacticalSystemService') || $tacticExisting < count($tacticCols)) {
		$tacticStatus = 'bad';
	}
	simtest_add_feature_row($featureRows, 'Grundtaktik & Pressing je Linie',
		$tacticStatus,
		'Defensiv-, Mittelfeld- und Angriffstaktik plus Pressinglinien fließen in Erfolgswahrscheinlichkeiten und Tickergruppen ein.',
		'Spalten: ' . $tacticExisting . '/' . count($tacticCols) . ' | Spiele mit Taktikprofil: ' . $tacticGames . ' | starkes Pressing: ' . $strongPressGames,
		($strongPressGames < 1 ? 'Ohne unterschiedliche Pressingprofile ist die Wirkung schwer sichtbar.' : 'Taktik-vs-Texttreffer unten zeigt, ob Profile andere Aktionen erzeugen.'),
		'Mehr Testspiele mit verschiedenen Profilen simulieren: hohe Linie+Pressing, tief+Konter, Kurzpass, Flügel.'
	);

	$dynamicsService = simtest_class_file_available('MatchSimulationDynamicsService');
	$zoneTicker = (simtest_has_column($db, 'matchreport', 'message_id') && simtest_has_column($db, 'spiel_text', 'aktion'))
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM matchreport MR INNER JOIN spiel_text ST ON ST.id = MR.message_id WHERE ST.aktion IN ('Seitenwechsel','pressing_interception') OR ST.aktion LIKE 'Duell_vor_Abschluss%'", 0)
		: 0;
	$dynamicsStatus = ($dynamicsService && $zoneTicker > 0) ? 'ok' : 'warn';
	if (!$dynamicsService) {
		$dynamicsStatus = 'bad';
	}
	simtest_add_feature_row($featureRows, 'Dynamik, Zonen & Spielerduelle',
		$dynamicsStatus,
		'Aktionen werden über Match-Dynamik, Duelle, Momentum und Aktionskontexte beeinflusst.',
		'Service: ' . ($dynamicsService ? 'vorhanden' : 'fehlt') . ' | passende Tickerereignisse: ' . $zoneTicker,
		($zoneTicker < 1 ? 'Interne Wirkung kann laufen, ist im Ticker aber noch kaum nachweisbar.' : 'Ticker zeigt Duelle/Pressing/Seitenwechsel als sichtbare Wirkung.'),
		'Bei zu wenig Sichtbarkeit mehr explizite Tickertexte für Zonenwechsel, Pressinggewinne und Duelle ergänzen.'
	);

	$cornerCols = simtest_existing_columns($db, 'spiel', array('home_corners','gast_corners','home_corner_left_player','home_corner_right_player','gast_corner_left_player','gast_corner_right_player'));
	$cornerGames = ($cornerCols >= 2)
		? (int) simtest_scalar($db, "SELECT COUNT(*) FROM spiel WHERE berechnet = '1' AND (COALESCE(home_corners,0) + COALESCE(gast_corners,0)) > 0", 0)
		: 0;
	$cornerAvg = ($cornerCols >= 2)
		? (float) simtest_scalar($db, "SELECT AVG(COALESCE(home_corners,0) + COALESCE(gast_corners,0)) FROM (SELECT home_corners, gast_corners FROM spiel WHERE berechnet = '1' ORDER BY datum DESC LIMIT 50) X", 0)
		: 0.0;
	$standardGoals = 0;
	$allTickerGoals = 0;
	$standardGoalPct = 0.0;
	if (simtest_has_column($db, 'matchreport', 'message_id') && simtest_has_column($db, 'matchreport', 'match_id') && simtest_has_column($db, 'spiel_text', 'aktion')) {
		$goalMixSql = "SELECT "
			. "SUM(CASE WHEN ST.aktion LIKE 'Elfmeter_erfolg%' "
			. "OR ST.aktion LIKE 'Freistoss_treffer%' "
			. "OR ST.aktion = 'Tor nach Vorlage Freistoß' "
			. "OR ST.aktion = 'Torwarttor bei Standard vorne' "
			. "OR ST.aktion LIKE 'Tor_mit_vorlage_Ecke%' "
			. "THEN 1 ELSE 0 END) AS standard_goals, "
			. "SUM(CASE WHEN ST.aktion LIKE 'Tor%' OR ST.aktion LIKE 'Tor_mit_vorlage%' "
			. "OR ST.aktion LIKE 'Elfmeter_erfolg%' OR ST.aktion LIKE 'Freistoss_treffer%' "
			. "OR ST.aktion = 'Tor nach Vorlage Freistoß' OR ST.aktion = 'Torwarttor bei Standard vorne' "
			. "THEN 1 ELSE 0 END) AS all_goals "
			. "FROM matchreport MR "
			. "INNER JOIN (SELECT id FROM spiel WHERE berechnet = '1' ORDER BY datum DESC LIMIT 200) L ON L.id = MR.match_id "
			. "INNER JOIN spiel_text ST ON ST.id = MR.message_id";
		$standardGoals = (int) simtest_scalar($db, "SELECT COALESCE(X.standard_goals,0) FROM (" . $goalMixSql . ") X", 0);
		$allTickerGoals = (int) simtest_scalar($db, "SELECT COALESCE(X.all_goals,0) FROM (" . $goalMixSql . ") X", 0);
		$standardGoalPct = ($allTickerGoals > 0) ? ($standardGoals * 100.0 / $allTickerGoals) : 0.0;
	}
	$cornerStatus = (simtest_class_file_available('CornerTacticService') && $cornerCols >= 6 && $cornerGames > 0 && $cornerAvg >= 4.0 && $cornerAvg <= 14.0 && ($allTickerGoals < 20 || $standardGoalPct >= 6.0)) ? 'ok' : 'warn';
	if (!simtest_class_file_available('CornerTacticService') || $cornerCols < 2) {
		$cornerStatus = 'bad';
	}
	simtest_add_feature_row($featureRows, 'Eckbälle & Standards',
		$cornerStatus,
		'Ecken werden gespeichert, können Spielerzuweisungen nutzen und berücksichtigen Kopfball-/Wetter-/Taktikfaktoren.',
		'Spalten: ' . $cornerCols . '/6 | Spiele mit Ecken: ' . $cornerGames . ' | Ø Ecken gesamt letzte 50: ' . number_format($cornerAvg, 2, ',', '.') . ' | Standardtore: ' . number_format($standardGoalPct, 1, ',', '.') . '%',
		(($cornerAvg > 14.0 || ($cornerGames > 0 && $cornerAvg < 4.0)) ? 'Eckenfrequenz wirkt außerhalb des realistischen Bereichs.' : (($allTickerGoals >= 20 && $standardGoalPct < 6.0) ? 'Standardtore sind im Ticker klar unterrepräsentiert.' : 'Eckenfrequenz und Standardtor-Anteil wirken grundsätzlich plausibel.')),
		'Eckenwerte mit sim_corner_miss_* und sim_corner_silent_* steuern; bei wenig Standardtoren Eckball-Verwertung und Freistoß-/Elfmeterpfade prüfen.'
	);

	$stateCols = simtest_existing_columns($db, 'spiel_berechnung', array('position_main','interceptions','recoveries','run_distance_m','shots_on_target','goalkeeper_parries'));
	$stateRows = (int) simtest_scalar($db, "SELECT COUNT(*) FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id WHERE S.berechnet = '1'", 0);
	$stateStatus = (simtest_class_file_available('SimulationStateHelper') && $stateCols === 6 && $stateRows > 0) ? 'ok' : 'warn';
	if (!simtest_class_file_available('SimulationStateHelper') || $stateCols < 4) {
		$stateStatus = 'bad';
	}
	simtest_add_feature_row($featureRows, 'Live-Fortsetzung & Statistikpersistenz',
		$stateStatus,
		'Zwischenstände, Taktik, Ecken und erweiterte Spieler-KPIs werden in spiel/spiel_berechnung gesichert.',
		'KPI-Spalten: ' . $stateCols . '/6 | gespeicherte Einsätze berechneter Spiele: ' . $stateRows,
		($stateRows < 1 ? 'Ohne gespeicherte Einsätze können Analyseblöcke keine Wirkung messen.' : 'Grundlage für Admin-Analyse, Spielerstatistik und Live-Fortsetzung ist vorhanden.'),
		'Wenn Werte leer bleiben: Cron/Queue prüfen und sicherstellen, dass Spiele vollständig berechnet werden.'
	);
} else {
	simtest_add_feature_row($featureRows, 'Datenbankzugriff', 'bad', 'Keine Analyse möglich.', 'mysqli-Verbindung fehlt.', 'Admin-Test kann keine Featurewirkung auswerten.', 'Datenbankverbindung im Admin-Kontext prüfen.');
}

foreach ($featureRows as $fr) {
	if ($fr['status'] === 'ok') {
		$featureOk++;
	} elseif ($fr['status'] === 'bad') {
		$featureBad++;
	} else {
		$featureWarn++;
	}
}

echo '<div class="alert alert-info">';
echo '<strong>Feature-Ampel:</strong> ' . (int) $featureOk . ' OK, ' . (int) $featureWarn . ' teilweise/pruefen, ' . (int) $featureBad . ' fehlt.';
echo '</div>';
echo '<table class="table table-striped table-bordered">';
echo '<thead><tr><th>Feature</th><th>Status</th><th>Was funktioniert?</th><th>Beleg</th><th>Problem / Lücke</th><th>Empfehlung</th></tr></thead><tbody>';
foreach ($featureRows as $fr) {
	echo '<tr>';
	echo '<td><strong>' . escapeOutput($fr['name']) . '</strong></td>';
	echo '<td>' . simtest_status_badge($fr['status']) . '</td>';
	echo '<td>' . escapeOutput($fr['works']) . '</td>';
	echo '<td>' . escapeOutput($fr['evidence']) . '</td>';
	echo '<td>' . escapeOutput($fr['risk']) . '</td>';
	echo '<td>' . escapeOutput($fr['recommendation']) . '</td>';
	echo '</tr>';
}
echo '</tbody></table>';

echo '<h2>Erweiterte KPI-Mittelwerte (letzte 50 Spiele)</h2>';
$extDone = false;
if (isset($db) && is_object($db) && isset($db->connection) && $db->connection instanceof mysqli) {
	$sqlExt = 'SELECT '
		. 'AVG(COALESCE(shoots,0)) AS shoots_avg, '
		. 'AVG(COALESCE(shots_on_target,0)) AS shots_on_target_avg, '
		. 'AVG(COALESCE(big_chances_missed,0)) AS big_chances_missed_avg, '
		. 'AVG(COALESCE(goals_inside_box,0)) AS goals_in_box_avg, '
		. 'AVG(COALESCE(goals_outside_box,0)) AS goals_out_box_avg, '
		. 'AVG(COALESCE(dribbles_won,0)) AS dribbles_won_avg, '
		. 'AVG(COALESCE(ball_losses,0)) AS ball_losses_avg, '
		. 'AVG(COALESCE(blocked_shots,0)) AS blocked_shots_avg, '
		. 'AVG(COALESCE(errors_leading_to_shots,0)) AS errors_shot_avg, '
		. 'AVG(COALESCE(errors_leading_to_goals,0)) AS errors_goal_avg, '
		. 'AVG(COALESCE(ball_wins_final_third,0)) AS wins_final_third_avg, '
		. 'AVG(COALESCE(recoveries,0)) AS recoveries_avg, '
		. 'AVG(COALESCE(saves_inside_box,0)) AS saves_in_box_avg, '
		. 'AVG(COALESCE(saves_outside_box,0)) AS saves_out_box_avg, '
		. 'AVG(COALESCE(goalkeeper_catches,0)) AS gk_catches_avg, '
		. 'AVG(COALESCE(goalkeeper_parries,0)) AS gk_parries_avg, '
		. 'AVG(COALESCE(sprint_duels_won,0)) AS sprint_duels_won_avg, '
		. 'AVG(COALESCE(run_distance_m,0)) AS run_distance_m_avg, '
		. '(SUM(COALESCE(run_distance_m,0)) / NULLIF(SUM(COALESCE(minuten_gespielt,0)),0) * 90) AS run_distance_per90_m '
		. 'FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id '
		. 'WHERE S.berechnet = \'1\' AND SB.minuten_gespielt > 0';
	$resExt = @$db->connection->query($sqlExt);
	if ($resExt && ($rowExt = $resExt->fetch_assoc())) {
		$extDone = true;
		echo '<table class="table table-bordered" style="max-width:760px;"><tbody>';
		$labels = array(
			'shoots_avg' => 'Ø Schüsse pro Spieler',
			'shots_on_target_avg' => 'Ø Schüsse aufs Tor pro Spieler',
			'big_chances_missed_avg' => 'Ø Großchancen vergeben',
			'goals_in_box_avg' => 'Ø Tore im Strafraum',
			'goals_out_box_avg' => 'Ø Tore außerhalb',
			'dribbles_won_avg' => 'Ø erfolgreiche Dribblings',
			'ball_losses_avg' => 'Ø Ballverluste',
			'blocked_shots_avg' => 'Ø geblockte Schüsse',
			'errors_shot_avg' => 'Ø Fehler, die zu Schüssen führten',
			'errors_goal_avg' => 'Ø Fehler, die zu Toren führten',
			'wins_final_third_avg' => 'Ø Ballgewinne (letztes Drittel)',
			'recoveries_avg' => 'Ø zurückgewonnene Bälle',
			'saves_in_box_avg' => 'Ø GK-Paraden im Strafraum',
			'saves_out_box_avg' => 'Ø GK-Paraden außerhalb',
			'gk_catches_avg' => 'Ø GK gefangene Bälle',
			'gk_parries_avg' => 'Ø GK parierte Bälle',
			'sprint_duels_won_avg' => 'Ø Sprintduelle gewonnen',
			'run_distance_m_avg' => 'Ø Laufdistanz (m)',
			'run_distance_per90_m' => 'Ø Laufdistanz pro 90 Min. (m)',
		);
		foreach ($labels as $k => $lab) {
			$val = isset($rowExt[$k]) ? number_format((float) $rowExt[$k], 2, ',', '.') : '0,00';
			echo '<tr><td>' . escapeOutput($lab) . '</td><td>' . escapeOutput($val) . '</td></tr>';
		}
		echo '</tbody></table>';
		$resExt->free();
	}
}
if (!$extDone) {
	echo '<p class="text-muted">Erweiterte KPI-Statistik aktuell nicht verfügbar.</p>';
}

echo '<h2>Positions-Zielmatrix (Ampel, letzte 1000 Einsätze)</h2>';
$matrixDone = false;
if (isset($db) && is_object($db) && isset($db->connection) && $db->connection instanceof mysqli) {
	$targetMatrix = array(
		'T' => array('saveq' => array(66, 100), 'run90' => array(2000, 5500), 'errg90' => array(0.00, 0.08)),
		'IV' => array('tackleq' => array(54, 100), 'recoveries90' => array(4.5, 14.0), 'losses90' => array(1.5, 7.5), 'run90' => array(7600, 12400), 'errg90' => array(0.00, 0.05)),
		'LV' => array('tackleq' => array(50, 100), 'recoveries90' => array(4.0, 12.0), 'losses90' => array(2.0, 9.5), 'run90' => array(9000, 13200), 'errg90' => array(0.00, 0.07)),
		'RV' => array('tackleq' => array(50, 100), 'recoveries90' => array(4.0, 12.0), 'losses90' => array(2.0, 9.5), 'run90' => array(9000, 13200), 'errg90' => array(0.00, 0.07)),
		'DM' => array('tackleq' => array(52, 100), 'recoveries90' => array(5.0, 15.0), 'losses90' => array(2.0, 8.5), 'run90' => array(9000, 13000), 'errg90' => array(0.00, 0.06)),
		'ZM' => array('tackleq' => array(47, 100), 'recoveries90' => array(3.8, 12.0), 'losses90' => array(2.5, 10.5), 'run90' => array(9800, 13800), 'errg90' => array(0.00, 0.08)),
		'OM' => array('gps' => array(12.0, 36.0), 'losses90' => array(3.0, 13.0), 'run90' => array(9200, 13200), 'shots90' => array(1.0, 4.5), 'errg90' => array(0.00, 0.10)),
		'LM' => array('gps' => array(9.0, 30.0), 'losses90' => array(3.0, 12.0), 'run90' => array(9800, 14000), 'shots90' => array(0.8, 3.5), 'errg90' => array(0.00, 0.10)),
		'RM' => array('gps' => array(9.0, 30.0), 'losses90' => array(3.0, 12.0), 'run90' => array(9800, 14000), 'shots90' => array(0.8, 3.5), 'errg90' => array(0.00, 0.10)),
		'LS' => array('gps' => array(14.0, 42.0), 'losses90' => array(3.5, 14.0), 'run90' => array(8600, 12600), 'shots90' => array(1.8, 6.0), 'errg90' => array(0.00, 0.12)),
		'RS' => array('gps' => array(14.0, 42.0), 'losses90' => array(3.5, 14.0), 'run90' => array(8600, 12600), 'shots90' => array(1.8, 6.0), 'errg90' => array(0.00, 0.12)),
		'MS' => array('gps' => array(16.0, 46.0), 'losses90' => array(3.5, 14.0), 'run90' => array(8200, 12200), 'shots90' => array(2.2, 6.5), 'errg90' => array(0.00, 0.12)),
	);

	$sqlMatrix = 'SELECT '
		. 'COALESCE(NULLIF(position_main, \'\'), \'ZM\') AS pm, '
		. 'COUNT(*) AS n, '
		. '(SUM(COALESCE(tore,0)) / NULLIF(SUM(COALESCE(shoots,0)),0) * 100.0) AS gps, '
		. '(SUM(COALESCE(wontackles,0)) / NULLIF(SUM(COALESCE(wontackles,0)+COALESCE(losttackles,0)),0) * 100.0) AS tackleq, '
		. '(SUM(COALESCE(shoots,0)) / NULLIF(SUM(COALESCE(minuten_gespielt,0)),0) * 90.0) AS shots90, '
		. '(SUM(COALESCE(ball_losses,0)) / NULLIF(SUM(COALESCE(minuten_gespielt,0)),0) * 90.0) AS losses90, '
		. '(SUM(COALESCE(recoveries,0)) / NULLIF(SUM(COALESCE(minuten_gespielt,0)),0) * 90.0) AS recoveries90, '
		. '(SUM(COALESCE(errors_leading_to_goals,0)) / NULLIF(SUM(COALESCE(minuten_gespielt,0)),0) * 90.0) AS errg90, '
		. '(SUM(COALESCE(saves,0)) / NULLIF(SUM(COALESCE(saves,0)+COALESCE(goals_conceded_inside_box,0)+COALESCE(goals_conceded_outside_box,0)),0) * 100.0) AS saveq, '
		. '(SUM(COALESCE(run_distance_m,0)) / NULLIF(SUM(COALESCE(minuten_gespielt,0)),0) * 90.0) AS run90 '
		. 'FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id '
		. 'WHERE S.berechnet = \'1\' AND SB.minuten_gespielt > 0 '
		. 'GROUP BY pm HAVING n >= 20 ORDER BY n DESC LIMIT 1000';
	$resMatrix = @$db->connection->query($sqlMatrix);
	if ($resMatrix) {
		$matrixDone = true;
		$rows = array();
		$baseline = array(
			'gps' => 0.0,
			'tackleq' => 0.0,
			'shots90' => 0.0,
			'losses90' => 0.0,
			'recoveries90' => 0.0,
			'run90' => 0.0,
			'errg90' => 0.0,
			'saveq' => 0.0,
		);
		$rowCount = 0;
		while ($r = $resMatrix->fetch_assoc()) {
			$rows[] = $r;
			$rowCount++;
			foreach ($baseline as $mk => $vv) {
				$baseline[$mk] += (float) ($r[$mk] ?? 0);
			}
		}
		if ($rowCount > 0) {
			foreach ($baseline as $mk => $vv) {
				$baseline[$mk] = $vv / $rowCount;
			}
		}
		echo '<table class="table table-striped table-bordered">';
		echo '<thead><tr><th>Position</th><th>Einsätze</th><th>Trefferquote</th><th>Zweikampfquote</th><th>Schüsse/90</th><th>Ballverluste/90</th><th>Recoveries/90</th><th>Laufdistanz/90 (m)</th><th>Fehler->Tor/90</th><th>Ampel Zielwert</th><th>Ampel Baseline</th></tr></thead><tbody>';
		foreach ($rows as $r) {
			$pm = isset($r['pm']) ? (string) $r['pm'] : 'ZM';
			if (!isset($targetMatrix[$pm])) {
				continue;
			}
			$targets = $targetMatrix[$pm];
			$score = 0;
			$checks = 0;
			foreach ($targets as $metric => $range) {
				$v = isset($r[$metric]) ? (float) $r[$metric] : 0.0;
				$checks++;
				if ($v >= (float) $range[0] && $v <= (float) $range[1]) {
					$score += 2;
				} elseif ($v >= (float) $range[0] * 0.88 && $v <= (float) $range[1] * 1.12) {
					$score += 1;
				}
			}
			$maxScore = max(1, $checks * 2);
			$ratio = $score / $maxScore;
			$signal = 'gelb';
			$signalCls = 'text-warning';
			if ($ratio >= 0.80) {
				$signal = 'gruen';
				$signalCls = 'text-success';
			} elseif ($ratio < 0.45) {
				$signal = 'rot';
				$signalCls = 'text-danger';
			}
			$baseScore = 0;
			$baseChecks = 0;
			foreach ($targets as $metric => $range) {
				$v = isset($r[$metric]) ? (float) $r[$metric] : 0.0;
				$b = isset($baseline[$metric]) ? (float) $baseline[$metric] : 0.0;
				if ($b <= 0.0) {
					continue;
				}
				$baseChecks++;
				$lower = $b * 0.88;
				$upper = $b * 1.12;
				if ($metric === 'errg90') {
					$lower = 0.0;
				}
				if ($v >= $lower && $v <= $upper) {
					$baseScore += 2;
				} elseif ($v >= ($b * 0.76) && $v <= ($b * 1.24)) {
					$baseScore += 1;
				}
			}
			$baseSignal = 'gelb';
			$baseSignalCls = 'text-warning';
			$baseRatio = ($baseChecks > 0) ? ($baseScore / ($baseChecks * 2)) : 0.5;
			if ($baseRatio >= 0.80) {
				$baseSignal = 'gruen';
				$baseSignalCls = 'text-success';
			} elseif ($baseRatio < 0.45) {
				$baseSignal = 'rot';
				$baseSignalCls = 'text-danger';
			}

			echo '<tr>';
			echo '<td><code>' . escapeOutput($pm) . '</code></td>';
			echo '<td>' . (int) ($r['n'] ?? 0) . '</td>';
			echo '<td>' . number_format((float) ($r['gps'] ?? 0), 1, ',', '.') . '%</td>';
			echo '<td>' . number_format((float) ($r['tackleq'] ?? 0), 1, ',', '.') . '%</td>';
			echo '<td>' . number_format((float) ($r['shots90'] ?? 0), 2, ',', '.') . '</td>';
			echo '<td>' . number_format((float) ($r['losses90'] ?? 0), 2, ',', '.') . '</td>';
			echo '<td>' . number_format((float) ($r['recoveries90'] ?? 0), 2, ',', '.') . '</td>';
			echo '<td>' . number_format((float) ($r['run90'] ?? 0), 0, ',', '.') . '</td>';
			echo '<td>' . number_format((float) ($r['errg90'] ?? 0), 3, ',', '.') . '</td>';
			echo '<td class="' . $signalCls . '">' . escapeOutput($signal) . '</td>';
			echo '<td class="' . $baseSignalCls . '">' . escapeOutput($baseSignal) . '</td>';
			echo '</tr>';
		}
		echo '</tbody></table>';
		$resMatrix->free();
	}
}
if (!$matrixDone) {
	echo '<p class="text-muted">Positions-Zielmatrix derzeit nicht verfügbar.</p>';
}

echo '<h2>Spielstil-Wirkung (Schnellcheck, letzte 1000 Einsätze)</h2>';
$styleDone = false;
if (isset($db) && is_object($db) && isset($db->connection) && $db->connection instanceof mysqli
		&& class_exists('PlayerPlaystyleCatalog')) {
	$styleBaseByPosition = array();
	$baseSql = 'SELECT COALESCE(NULLIF(position_main, \'\'), \'ZM\') AS pm, '
		. 'COUNT(*) AS n, AVG(COALESCE(note,0)) AS g, '
		. 'SUM(COALESCE(tore,0)) AS gs, SUM(COALESCE(shoots,0)) AS ss, '
		. 'SUM(COALESCE(wontackles,0)) AS tw, '
		. 'SUM(COALESCE(passes_successed,0)) AS ps, SUM(COALESCE(passes_failed,0)) AS pf '
		. 'FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id '
		. 'WHERE S.berechnet = \'1\' AND SB.minuten_gespielt > 0 '
		. 'GROUP BY pm';
	$baseRes = @$db->connection->query($baseSql);
	if ($baseRes) {
		while ($baseRow = $baseRes->fetch_assoc()) {
			$pm = (string) ($baseRow['pm'] ?? 'ZM');
			$ps = (float) ($baseRow['ps'] ?? 0);
			$pf = (float) ($baseRow['pf'] ?? 0);
			$ss = (float) ($baseRow['ss'] ?? 0);
			$nBase = max(1.0, (float) ($baseRow['n'] ?? 1));
			$styleBaseByPosition[$pm] = array(
				'grade' => (float) ($baseRow['g'] ?? 0),
				'goal_per_shot' => ($ss > 0.0) ? ((float) ($baseRow['gs'] ?? 0) * 100.0 / $ss) : 0.0,
				'passq' => (($ps + $pf) > 0.0) ? ($ps * 100.0 / ($ps + $pf)) : 0.0,
				'tackles_per_use' => (float) ($baseRow['tw'] ?? 0) / $nBase,
			);
		}
		$baseRes->free();
	}
	$sqlStyles = 'SELECT sid, COALESCE(NULLIF(position_main, \'\'), \'ZM\') AS pm, COUNT(*) AS n, '
		. 'AVG(COALESCE(note,0)) AS grade_avg, '
		. 'SUM(COALESCE(tore,0)) AS goals_sum, '
		. 'SUM(COALESCE(shoots,0)) AS shoots_sum, '
		. 'SUM(COALESCE(wontackles,0)) AS tackles_won_sum, '
		. 'SUM(COALESCE(passes_successed,0)) AS pass_ok_sum, '
		. 'SUM(COALESCE(passes_failed,0)) AS pass_fail_sum '
		. 'FROM ('
		. 'SELECT SB.*, P.ps_1 AS sid FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id INNER JOIN spieler P ON P.id = SB.spieler_id WHERE S.berechnet = \'1\' AND P.ps_1 IS NOT NULL AND P.ps_1 != \'\' '
		. 'UNION ALL '
		. 'SELECT SB.*, P.ps_2 AS sid FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id INNER JOIN spieler P ON P.id = SB.spieler_id WHERE S.berechnet = \'1\' AND P.ps_2 IS NOT NULL AND P.ps_2 != \'\' '
		. 'UNION ALL '
		. 'SELECT SB.*, P.ps_3 AS sid FROM spiel_berechnung SB INNER JOIN spiel S ON S.id = SB.spiel_id INNER JOIN spieler P ON P.id = SB.spieler_id WHERE S.berechnet = \'1\' AND P.ps_3 IS NOT NULL AND P.ps_3 != \'\' '
		. ') X GROUP BY sid, pm HAVING n >= 20 ORDER BY n DESC LIMIT 30';
	$resStyles = @$db->connection->query($sqlStyles);
	if ($resStyles) {
		$styleDone = true;
		echo '<table class="table table-striped table-bordered">';
		echo '<thead><tr><th>Stil</th><th>Position</th><th>Einsätze</th><th>Ø Note</th><th>Tore/Schuss</th><th>Passquote</th><th>Gew. Zweikämpfe</th><th>Ampel</th></tr></thead><tbody>';
		while ($r = $resStyles->fetch_assoc()) {
			$sid = isset($r['sid']) ? (string) $r['sid'] : '';
			$pm = isset($r['pm']) ? (string) $r['pm'] : 'ZM';
			$label = PlayerPlaystyleCatalog::getLabel($sid);
			$n = (int) ($r['n'] ?? 0);
			$grade = number_format((float) ($r['grade_avg'] ?? 0), 2, ',', '.');
			$g = (float) ($r['goals_sum'] ?? 0);
			$sh = max(1.0, (float) ($r['shoots_sum'] ?? 0));
			$gPerSh = number_format(($g / $sh) * 100.0, 1, ',', '.') . '%';
			$pok = (float) ($r['pass_ok_sum'] ?? 0);
			$pfail = (float) ($r['pass_fail_sum'] ?? 0);
			$passAttempts = $pok + $pfail;
			if ($passAttempts < 20.0) {
				continue;
			}
			$pq = number_format(($pok + $pfail) > 0 ? ($pok * 100.0 / ($pok + $pfail)) : 0, 1, ',', '.') . '%';
			$pqNum = (($pok + $pfail) > 0 ? ($pok * 100.0 / ($pok + $pfail)) : 0.0);
			$tw = (int) ($r['tackles_won_sum'] ?? 0);
			$twPerUse = ($n > 0) ? ((float) $tw / (float) $n) : 0.0;
			$gradeNum = (float) ($r['grade_avg'] ?? 0);
			$gPerShNum = ($g / $sh) * 100.0;
			$base = isset($styleBaseByPosition[$pm]) ? $styleBaseByPosition[$pm] : array('grade' => 0.0, 'goal_per_shot' => 0.0, 'passq' => 0.0, 'tackles_per_use' => 0.0);
			$signal = 'neutral';
			$signalCls = 'text-muted';
			$score = 0;
			$offensiveMain = in_array($pm, array('MS','LS','RS','OM','LM','RM'), true);
			if ($offensiveMain && (float) $base['goal_per_shot'] > 0 && $gPerShNum >= (float) $base['goal_per_shot'] * 1.10) { $score++; }
			if ((float) $base['passq'] > 0 && $pqNum >= (float) $base['passq'] * 0.98) { $score++; }
			if ((float) $base['tackles_per_use'] > 0 && $twPerUse >= (float) $base['tackles_per_use'] * 1.05) { $score++; }
			if ((float) $base['grade'] > 0 && $gradeNum <= max(1.0, (float) $base['grade'] - 0.08)) { $score++; } // kleinere Note ist besser
			if ($score >= 2) {
				$signal = 'overperform';
				$signalCls = 'text-success';
			} elseif ((float) $base['grade'] > 0 && $gradeNum >= (float) $base['grade'] + 0.18
					&& (float) $base['passq'] > 0 && $pqNum <= (float) $base['passq'] * 0.92
					&& (float) $base['tackles_per_use'] > 0 && $twPerUse <= (float) $base['tackles_per_use'] * 0.90) {
				$signal = 'underperform';
				$signalCls = 'text-danger';
			}
			echo '<tr>';
			echo '<td><code>' . escapeOutput($sid) . '</code> — ' . escapeOutput($label) . '</td>';
			echo '<td><code>' . escapeOutput($pm) . '</code></td>';
			echo '<td>' . $n . '</td>';
			echo '<td>' . $grade . '</td>';
			echo '<td>' . $gPerSh . '</td>';
			echo '<td>' . $pq . '</td>';
			echo '<td>' . $tw . '</td>';
			echo '<td class="' . $signalCls . '">' . escapeOutput($signal) . '</td>';
			echo '</tr>';
		}
		echo '</tbody></table>';
		$resStyles->free();
	}
}
if (!$styleDone) {
	echo '<p class="text-muted">Spielstil-Schnellcheck derzeit nicht verfügbar.</p>';
}

echo '<h2>Liveticker-Abdeckung (Spielberichtsmeldungen)</h2>';
echo '<p class="muted small">Vergleicht <code>spiel_text</code> (alle Texte/Aktionen) mit tatsächlichen Einträgen in <code>matchreport</code>. '
	. 'Hilft zu finden, warum z. B. Torwart-vorne, Elfmeter-Varianten oder späte Tore selten/nie im Liveticker erscheinen.</p>';

$ltMatchLimit = isset($_GET['lt_limit']) ? (int) $_GET['lt_limit'] : 200;
$ltMatchId = isset($_GET['lt_match']) ? (int) $_GET['lt_match'] : 0;
$ltFilter = isset($_GET['lt_filter']) ? trim((string) $_GET['lt_filter']) : '';
$ltShowUnused = !isset($_GET['lt_hide_unused']) || (string) $_GET['lt_hide_unused'] !== '1';

echo '<form method="get" class="form-inline" style="margin-bottom:14px;">';
echo '<input type="hidden" name="site" value="' . escapeOutput($site) . '">';
echo '<label>Spiele </label> <input type="number" name="lt_limit" value="' . (int) $ltMatchLimit . '" min="10" max="2000" class="input-small" style="width:70px;margin:0 8px;">';
echo '<label>oder Spiel-ID </label> <input type="number" name="lt_match" value="' . (int) $ltMatchId . '" min="0" class="input-small" style="width:90px;margin:0 8px;">';
echo '<label>Filter Aktion </label> <input type="text" name="lt_filter" value="' . escapeOutput($ltFilter) . '" placeholder="z.B. Elfmeter, Torwart" class="input-medium" style="margin:0 8px;">';
echo '<label class="checkbox" style="margin-left:8px;"><input type="checkbox" name="lt_hide_unused" value="1"' . ($ltShowUnused ? '' : ' checked') . '> Liste „nie ausgelöst“ ausblenden</label> ';
echo '<button type="submit" class="btn">Aktualisieren</button>';
echo '</form>';

$diagDone = false;
if (isset($db) && is_object($db) && isset($db->connection) && $db->connection instanceof mysqli) {
	if (!class_exists('LivetickerCoverageDiagnosticsService', false)) {
		require_once BASE_FOLDER . '/classes/services/LivetickerCoverageDiagnosticsService.class.php';
	}
	try {
		$ltReport = LivetickerCoverageDiagnosticsService::buildReport($db, $ltMatchLimit, $ltMatchId);
		LivetickerCoverageDiagnosticsService::renderHtml($ltReport, $ltFilter, $ltShowUnused);
		$diagDone = true;
	} catch (Throwable $e) {
		echo '<p class="text-danger">Liveticker-Abdeckung: ' . escapeOutput($e->getMessage()) . '</p>';
	}

	$diagMatchLimit = $ltMatchLimit;
	$sqlActions = 'SELECT ST.aktion AS aktion, COUNT(*) AS c '
		. 'FROM matchreport MR '
		. 'INNER JOIN (SELECT id FROM spiel WHERE berechnet = \'1\' ORDER BY datum DESC LIMIT ' . (int) $diagMatchLimit . ') L ON L.id = MR.match_id '
		. 'INNER JOIN spiel_text ST ON ST.id = MR.message_id '
		. 'GROUP BY ST.aktion ORDER BY c DESC LIMIT 25';
	$resActions = @$db->connection->query($sqlActions);
	if ($resActions) {
		$diagDone = true;
		echo '<h3>Top genutzte Aktionen</h3>';
		echo '<table class="table table-striped table-bordered" style="max-width:760px;">';
		echo '<thead><tr><th>Aktion</th><th>Vorkommen</th></tr></thead><tbody>';
		while ($r = $resActions->fetch_assoc()) {
			echo '<tr>';
			echo '<td><code>' . escapeOutput((string) ($r['aktion'] ?? '')) . '</code></td>';
			echo '<td>' . (int) ($r['c'] ?? 0) . '</td>';
			echo '</tr>';
		}
		echo '</tbody></table>';
		$resActions->free();
	}

	$sqlTexts = 'SELECT ST.aktion AS aktion, ST.id AS text_id, LEFT(ST.nachricht, 120) AS msg, COUNT(*) AS c '
		. 'FROM matchreport MR '
		. 'INNER JOIN (SELECT id FROM spiel WHERE berechnet = \'1\' ORDER BY datum DESC LIMIT ' . (int) $diagMatchLimit . ') L ON L.id = MR.match_id '
		. 'INNER JOIN spiel_text ST ON ST.id = MR.message_id '
		. 'GROUP BY ST.id, ST.aktion, ST.nachricht '
		. 'ORDER BY c DESC LIMIT 30';
	$resTexts = @$db->connection->query($sqlTexts);
	if ($resTexts) {
		$diagDone = true;
		echo '<h3>Top genutzte Text-IDs</h3>';
		echo '<table class="table table-striped table-bordered">';
		echo '<thead><tr><th>Aktion</th><th>Text-ID</th><th>Vorkommen</th><th>Text (gekürzt)</th></tr></thead><tbody>';
		while ($r = $resTexts->fetch_assoc()) {
			echo '<tr>';
			echo '<td><code>' . escapeOutput((string) ($r['aktion'] ?? '')) . '</code></td>';
			echo '<td>' . (int) ($r['text_id'] ?? 0) . '</td>';
			echo '<td>' . (int) ($r['c'] ?? 0) . '</td>';
			echo '<td>' . escapeOutput((string) ($r['msg'] ?? '')) . '</td>';
			echo '</tr>';
		}
		echo '</tbody></table>';
		$resTexts->free();
	}

	$sqlScorers = 'SELECT CONCAT(COALESCE(P.vorname, \'\'), \' \', COALESCE(P.nachname, \'\')) AS pname, '
		. 'SUM(COALESCE(SB.tore,0)) AS goals, COUNT(DISTINCT SB.spiel_id) AS matches '
		. 'FROM spiel_berechnung SB '
		. 'INNER JOIN (SELECT id FROM spiel WHERE berechnet = \'1\' ORDER BY datum DESC LIMIT ' . (int) $diagMatchLimit . ') L ON L.id = SB.spiel_id '
		. 'LEFT JOIN spieler P ON P.id = SB.spieler_id '
		. 'GROUP BY SB.spieler_id, P.vorname, P.nachname '
		. 'HAVING goals > 0 '
		. 'ORDER BY goals DESC, matches DESC LIMIT 20';
	$sqlGoalMix = 'SELECT '
		. 'SUM(CASE '
		. 'WHEN ST.aktion LIKE \'Elfmeter_erfolg%\' '
		. 'OR ST.aktion LIKE \'Freistoss_treffer%\' '
		. 'OR ST.aktion = \'Tor nach Vorlage Freistoß\' '
		. 'OR ST.aktion = \'Torwarttor bei Standard vorne\' '
		. 'OR ST.aktion LIKE \'Tor_mit_vorlage_Ecke%\' '
		. 'THEN 1 ELSE 0 END) AS standards_goals, '
		. 'SUM(CASE '
		. 'WHEN ST.aktion LIKE \'Tor%\' OR ST.aktion LIKE \'Tor_mit_vorlage%\' '
		. 'OR ST.aktion LIKE \'Elfmeter_erfolg%\' OR ST.aktion LIKE \'Freistoss_treffer%\' '
		. 'OR ST.aktion = \'Tor nach Vorlage Freistoß\' OR ST.aktion = \'Torwarttor bei Standard vorne\' '
		. 'THEN 1 ELSE 0 END) AS all_goal_events '
		. 'FROM matchreport MR '
		. 'INNER JOIN (SELECT id FROM spiel WHERE berechnet = \'1\' ORDER BY datum DESC LIMIT ' . (int) $diagMatchLimit . ') L ON L.id = MR.match_id '
		. 'INNER JOIN spiel_text ST ON ST.id = MR.message_id';
	$resGoalMix = @$db->connection->query($sqlGoalMix);
	if ($resGoalMix && ($mix = $resGoalMix->fetch_assoc())) {
		$diagDone = true;
		$standards = (int) ($mix['standards_goals'] ?? 0);
		$allGoals = (int) ($mix['all_goal_events'] ?? 0);
		$openPlay = max(0, $allGoals - $standards);
		$openPct = ($allGoals > 0) ? round($openPlay * 100.0 / $allGoals, 1) : 0;
		$stdPct = ($allGoals > 0) ? round($standards * 100.0 / $allGoals, 1) : 0;
		echo '<h3>Open-Play vs Standards (aus Ticker-Toren)</h3>';
		echo '<table class="table table-striped table-bordered" style="max-width:760px;">';
		echo '<thead><tr><th>Kategorie</th><th>Anzahl</th><th>Anteil</th></tr></thead><tbody>';
		echo '<tr><td>Open Play</td><td>' . $openPlay . '</td><td>' . number_format($openPct, 1, ',', '.') . '%</td></tr>';
		echo '<tr><td>Standards (Freistoß/Elfmeter/Ecke/Standard-Sonderfall)</td><td>' . $standards . '</td><td>' . number_format($stdPct, 1, ',', '.') . '%</td></tr>';
		echo '<tr><td><strong>Gesamt</strong></td><td><strong>' . $allGoals . '</strong></td><td>100,0%</td></tr>';
		echo '</tbody></table>';
		$resGoalMix->free();
	}
	$sqlTacticTextFit = 'SELECT tactic_profile, action_group, COUNT(*) AS c '
		. 'FROM ('
		. 'SELECT '
		. 'CONCAT('
		. 'CASE WHEN MR.active_home = 1 THEN COALESCE(NULLIF(S.home_tactic_def, \'\'), \'deep_line\') ELSE COALESCE(NULLIF(S.gast_tactic_def, \'\'), \'deep_line\') END, '
		. '\' / \', '
		. 'CASE WHEN MR.active_home = 1 THEN COALESCE(NULLIF(S.home_tactic_mid, \'\'), \'short_passing\') ELSE COALESCE(NULLIF(S.gast_tactic_mid, \'\'), \'short_passing\') END, '
		. '\' / \', '
		. 'CASE WHEN MR.active_home = 1 THEN COALESCE(NULLIF(S.home_tactic_att, \'\'), \'wings\') ELSE COALESCE(NULLIF(S.gast_tactic_att, \'\'), \'wings\') END'
		. ') AS tactic_profile, '
		. 'CASE '
		. 'WHEN ST.aktion LIKE \'Tor%\' OR ST.aktion LIKE \'Tor_mit_vorlage%\' OR ST.aktion LIKE \'Torschuss%\' THEN \'Tor/Abschluss\' '
		. 'WHEN ST.aktion LIKE \'Pass_daneben%\' OR ST.aktion = \'Seitenwechsel\' THEN \'Pass-/Aufbauspiel\' '
		. 'WHEN ST.aktion LIKE \'Zweikampf%\' OR ST.aktion LIKE \'Duell_vor_Abschluss%\' THEN \'Zweikampf/Pressing\' '
		. 'WHEN ST.aktion LIKE \'Ecke%\' OR ST.aktion LIKE \'Freistoss%\' OR ST.aktion LIKE \'Elfmeter%\' OR ST.aktion LIKE \'Torwart%Standard%\' THEN \'Standards\' '
		. 'WHEN ST.aktion LIKE \'Karte%\' THEN \'Karten/Disziplin\' '
		. 'WHEN ST.aktion LIKE \'Verletzung%\' THEN \'Verletzungen\' '
		. 'ELSE \'Sonstiges\' '
		. 'END AS action_group '
		. 'FROM matchreport MR '
		. 'INNER JOIN (SELECT id, home_tactic_def, home_tactic_mid, home_tactic_att, gast_tactic_def, gast_tactic_mid, gast_tactic_att '
		. 'FROM spiel WHERE berechnet = \'1\' ORDER BY datum DESC LIMIT ' . (int) $diagMatchLimit . ') S ON S.id = MR.match_id '
		. 'INNER JOIN spiel_text ST ON ST.id = MR.message_id '
		. ') X '
		. 'GROUP BY tactic_profile, action_group '
		. 'HAVING c >= 5 '
		. 'ORDER BY tactic_profile ASC, c DESC '
		. 'LIMIT 400';
	$resTacticTextFit = @$db->connection->query($sqlTacticTextFit);
	if ($resTacticTextFit) {
		$diagDone = true;
		$byProfile = array();
		while ($r = $resTacticTextFit->fetch_assoc()) {
			$p = (string) ($r['tactic_profile'] ?? '');
			$g = (string) ($r['action_group'] ?? '');
			$c = (int) ($r['c'] ?? 0);
			if ($p === '' || $g === '' || $c < 1) {
				continue;
			}
			if (!isset($byProfile[$p])) {
				$byProfile[$p] = array(
					'total' => 0,
					'groups' => array(),
				);
			}
			$byProfile[$p]['total'] += $c;
			$byProfile[$p]['groups'][$g] = $c;
		}
		$resTacticTextFit->free();

		if (count($byProfile)) {
			uasort($byProfile, function ($a, $b) {
				return (int) ($b['total'] ?? 0) <=> (int) ($a['total'] ?? 0);
			});
			echo '<h3>Taktik vs. Texttreffer (aktive Team-Taktik je Meldung)</h3>';
			echo '<p class="muted small">Zeigt pro Taktik-Profil die häufigsten Aktionsgruppen im Ticker (letzte ' . (int) $diagMatchLimit . ' berechnete Spiele).</p>';
			echo '<table class="table table-striped table-bordered">';
			echo '<thead><tr><th>Taktikprofil (Def / Mid / Angriff)</th><th>Top-Aktionsgruppen</th><th>Meldungen gesamt</th></tr></thead><tbody>';
			$shownProfiles = 0;
			foreach ($byProfile as $profile => $bucket) {
				if ($shownProfiles >= 14) {
					break;
				}
				$groups = isset($bucket['groups']) && is_array($bucket['groups']) ? $bucket['groups'] : array();
				if (!count($groups)) {
					continue;
				}
				arsort($groups);
				$parts = array();
				$i = 0;
				foreach ($groups as $g => $cnt) {
					$parts[] = escapeOutput((string) $g) . ': ' . (int) $cnt;
					$i++;
					if ($i >= 5) {
						break;
					}
				}
				echo '<tr>';
				echo '<td><code>' . escapeOutput($profile) . '</code></td>';
				echo '<td>' . implode(' | ', $parts) . '</td>';
				echo '<td>' . (int) ($bucket['total'] ?? 0) . '</td>';
				echo '</tr>';
				$shownProfiles++;
			}
			echo '</tbody></table>';
		}
	}
	$resScorers = @$db->connection->query($sqlScorers);
	if ($resScorers) {
		$diagDone = true;
		echo '<h3>Top-Torschützen (Open Play + Standards zusammen)</h3>';
		echo '<table class="table table-striped table-bordered" style="max-width:760px;">';
		echo '<thead><tr><th>Spieler</th><th>Tore</th><th>Spiele mit Einsatz</th></tr></thead><tbody>';
		while ($r = $resScorers->fetch_assoc()) {
			$pn = trim((string) ($r['pname'] ?? ''));
			if ($pn === '') {
				$pn = 'Unbekannt';
			}
			echo '<tr>';
			echo '<td>' . escapeOutput($pn) . '</td>';
			echo '<td>' . (int) ($r['goals'] ?? 0) . '</td>';
			echo '<td>' . (int) ($r['matches'] ?? 0) . '</td>';
			echo '</tr>';
		}
		echo '</tbody></table>';
		$resScorers->free();
	}
}
if (!$diagDone) {
	echo '<p class="text-muted">Liveticker-Diagnose aktuell nicht verfügbar.</p>';
}

echo '<p><strong>Zusammenfassung:</strong> ' . (int) $ok . ' Werte im Zielbereich, ' . (int) $warn . ' mit Anpassungsbedarf.</p>';
echo '<p><a href="?site=all_settings">→ Zu allen Einstellungen</a> (Simulation &amp; Experten-Kategorie)</p>';
