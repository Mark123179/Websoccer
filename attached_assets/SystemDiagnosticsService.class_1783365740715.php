<?php
/******************************************************
 * Zentrale System-Diagnose: Jobs, Simulation, Logs, Liveticker, Sponsoren.
 ******************************************************/

class SystemDiagnosticsService {

	/**
	 * @return array{sections:array<int,array<string,mixed>>,summary:array<string,int>}
	 */
	public static function runFullReport(WebSoccer $websoccer, DbConnection $db, array $options = array()) {
		$clubId = isset($options['club_id']) ? (int) $options['club_id'] : 0;
		$livetickerLimit = isset($options['liveticker_limit']) ? (int) $options['liveticker_limit'] : 100;

		$sections = array(
			self::sectionFeatureOverview($db),
			self::sectionDevelopmentSystem($db),
			self::sectionForumSystems($db),
			self::sectionModuleInventory(),
			self::sectionJobs(),
			self::sectionSimulation($db),
			self::sectionLogs(),
			self::sectionPhpEnvironment(),
			self::sectionLiveticker($db, $livetickerLimit),
			self::sectionSponsors($websoccer, $db, $clubId),
			self::sectionConfigHints(),
		);

		$summary = array('error' => 0, 'warn' => 0, 'ok' => 0, 'info' => 0);
		foreach ($sections as $sec) {
			foreach ((array) ($sec['items'] ?? array()) as $item) {
				$lvl = (string) ($item['level'] ?? 'info');
				if (!isset($summary[$lvl])) {
					$summary[$lvl] = 0;
				}
				$summary[$lvl]++;
			}
		}

		return array('sections' => $sections, 'summary' => $summary);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionFeatureOverview(DbConnection $db) {
		$features = array(
			array(
				'name' => 'Match Engine / Spielberechnung',
				'classes' => array(
					'MatchSimulationExecutor',
					'SimulationStateHelper',
					'DataUpdateSimulatorObserver',
					'PlayerPerformanceScoreService',
				),
				'tables' => array('spiel', 'spiel_berechnung'),
				'columns' => array(
					'spiel.berechnet',
					'spiel.blocked',
					'spiel.minutes',
					'spiel_berechnung.spieler_id',
					'spiel_berechnung.note',
					'spiel_berechnung.minuten_gespielt',
					'spiel_berechnung.performance_score',
				),
				'admin_pages' => array('simulationtest', 'match-commentary-management', 'cup-match-diagnostics'),
				'configs' => array('sim_interval', 'sim_batch_cap_enabled', 'sim_skip_kickoff_delay'),
			),
			array(
				'name' => 'Spielerentwicklung / Marktwert entkoppelt',
				'classes' => array(
					'PlayerPotentialService',
					'PlayerPerformanceScoreService',
					'MarketValueStrengthSystemService',
					'PlayerAttributeDefinitionService',
					'PlayerGlobalAttributeService',
				),
				'tables' => array('spieler'),
				'columns' => array(
					'spieler.w_staerke',
					'spieler.potenzial',
					'spieler.potential_band_min',
					'spieler.potential_band_max',
					'spieler.talent',
					'spieler.development_rate',
					'spieler.development_points',
					'spieler.last_performance_score',
				),
				'admin_pages' => array('player-attributes-tools', 'teamsgenerator'),
				'configs' => array('player_performance_development_enabled', 'market_value_development_enabled'),
			),
			array(
				'name' => 'Transfermarkt / FMinside Import',
				'classes' => array('TransfermarktImportService'),
				'tables' => array('verein', 'spieler', 'youthplayer'),
				'columns' => array(
					'verein.transfermarkt_verein_id',
					'verein.fminside_club_url',
					'spieler.transfermarkt_player_id',
					'spieler.fminside_player_id',
					'spieler.fminside_player_url',
					'spieler.fminside_rating',
					'spieler.fminside_potential',
					'spieler.fminside_attributes_json',
				),
				'admin_pages' => array('teamsgenerator', 'playersgenerator', 'u19-senior-backfill'),
				'configs' => array('transfermarkt_import_enabled', 'fminside_import_enabled'),
			),
			array(
				'name' => 'Jugend, Jugendscouting und Jugendcamp',
				'classes' => array(
					'YouthPlayersDataService',
					'YouthMatchesDataService',
					'YouthMatchSimulationExecutor',
					'YouthMatchDataUpdateSimulatorObserver',
					'YouthScoutingMissionService',
					'YouthCampDataService',
				),
				'tables' => array(
					'youthplayer',
					'youthmatch',
					'youthmatch_player',
					'youthscout',
					'youth_scout_mission',
					'youth_scout_candidate',
					'youthcamp',
					'youthcamp_team',
					'youthcamp_offer',
				),
				'columns' => array(
					'youthplayer.strength',
					'youthplayer.potenzial',
					'youthplayer.talent',
					'youthplayer.development_rate',
					'youthplayer.development_points',
					'youthplayer.pro_readiness',
					'youthplayer.last_performance_score',
					'youthmatch_player.performance_score',
				),
				'admin_pages' => array(
					'youth-match-diagnostics',
					'youth-scout-missions',
					'youth-scout-sources',
					'youth-scout-portraits',
					'youth-league-generator',
					'youth-skills-backfill',
				),
				'configs' => array('youth_enabled', 'youth_scouting_enabled', 'youthcamp_enabled'),
			),
			array(
				'name' => 'Scouting / Spielerbeobachtung',
				'classes' => array(
					'ScoutingPoolDataService',
					'ScoutingScoutDataService',
					'ScoutingWatchlistDataService',
					'ScoutingSearchOrderDataService',
					'ScoutingRegionNetworkDataService',
				),
				'tables' => array(
					'scouting_pool_sources',
					'scouting_pool_players',
					'scouting_pool_discoveries',
					'scouting_scouts',
					'scouting_club_scouts',
					'scouting_watchlist',
					'scouting_search_order',
					'scouting_region_network',
				),
				'admin_pages' => array('scouting-pool', 'scouting-scouts', 'scouting-pool-bulk-import', 'scouting-scout-bulk-import'),
				'configs' => array('scouting_enabled'),
			),
			array(
				'name' => 'KI-Transfers / Auktionen',
				'classes' => array(
					'AiTransferIntegrationService',
					'AiTransferSchemaService',
					'AiTransferMarketService',
					'PlayerAuctionDataService',
					'PlayerAuctionBidAuditService',
				),
				'tables' => array('ai_club_profiles', 'ai_transfer_targets', 'ai_transfer_activity', 'player_auction', 'player_auction_bid'),
				'admin_pages' => array('ai-transfer-admin', 'player-auction-create', 'player-auction-bid-audit'),
				'configs' => array('ai_transfer_enabled', 'playerauction_enabled', 'playerauction_default_min_bid', 'playerauction_default_max_bid'),
			),
			array(
				'name' => 'Vorstand / Managerentlassung',
				'classes' => array('BoardManagementService', 'BoardManagementJob'),
				'tables' => array('verein', 'user', 'verein_board_state'),
				'columns' => array('user.club_takeover_banned_until', 'user.last_voluntary_resign_season', 'user.last_voluntary_resign_at'),
				'admin_pages' => array('board-management', 'club-manager-overview'),
				'configs' => array('board_system_enabled', 'board_sender_name', 'board_takeover_ban_hours'),
			),
			array(
				'name' => 'Sponsoren / Stadion',
				'classes' => array('SponsorsDataService', 'StadiumSponsoringDataService'),
				'tables' => array('sponsor', 'club_sponsor_contract', 'stadium_sponsor'),
				'admin_pages' => array('sponsor-bulk-import', 'stadium-sponsoring-bulk-import', 'stadiumbuilder-bulk-import'),
				'configs' => array('sponsor_earliest_matchday', 'sponsor_earliest_cup_matches'),
			),
			array(
				'name' => 'News, Storylines und Social Feed',
				'classes' => array('LeagueNewsDataService', 'CompetitionAutoNewsService', 'LeagueCentralNewsService', 'SocialFeedDataService'),
				'tables' => array('league_news', 'league_news_block', 'competition_auto_news_cfg', 'competition_auto_news_log', 'league_system_news', 'social_feed_post'),
				'admin_pages' => array('league-news-admin', 'competition-auto-news-admin', 'league-storyline-admin', 'social-feed-reports'),
				'configs' => array('league_news_enabled', 'social_feed_enabled'),
			),
		);

		$items = array();
		foreach ($features as $feature) {
			$items[] = self::featureStatusItem($db, $feature);
		}
		return self::wrapSection('feature-overview', 'Feature-Ampel (alle Kernbereiche)', self::severityFromItems($items), $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionDevelopmentSystem(DbConnection $db) {
		$items = array();
		$proCols = array(
			'w_staerke',
			'potenzial',
			'potential_band_min',
			'potential_band_max',
			'talent',
			'form',
			'selbstvertrauen',
			'development_rate',
			'development_points',
			'pro_readiness',
			'last_performance_score',
			'fminside_rating',
			'fminside_potential',
		);
		$missingPro = self::missingColumns($db, 'spieler', $proCols);
		$items[] = self::item(
			count($missingPro) ? 'error' : 'ok',
			'Profis: Entwicklungsdaten',
			count($missingPro) ? 'Fehlende Spalten in spieler: ' . implode(', ', $missingPro) : 'Stärke, Talent, Potential, Form, Entwicklungstempo und Performance Score sind vorhanden.'
		);

		$youthCols = array(
			'strength',
			'potenzial',
			'potential_band_min',
			'potential_band_max',
			'talent',
			'development_rate',
			'development_points',
			'pro_readiness',
			'last_performance_score',
		);
		$missingYouth = self::missingColumns($db, 'youthplayer', $youthCols);
		$items[] = self::item(
			count($missingYouth) ? 'warn' : 'ok',
			'Jugendspieler: Entwicklungsdaten',
			count($missingYouth) ? 'Fehlende Spalten in youthplayer: ' . implode(', ', $missingYouth) : 'Jugendstärke, Talent, Potential, Entwicklungstempo und Profi-Reife sind vorhanden.'
		);

		$missingMatch = self::missingColumns($db, 'spiel_berechnung', array('performance_score', 'minuten_gespielt', 'note'));
		$missingYouthMatch = self::missingColumns($db, 'youthmatch_player', array('performance_score', 'minuten_gespielt', 'note'));
		$items[] = self::item(
			(count($missingMatch) || count($missingYouthMatch)) ? 'warn' : 'ok',
			'Performance Score nach Spielen',
			(count($missingMatch) || count($missingYouthMatch))
				? 'Fehlende Match-Spalten: Profis [' . implode(', ', $missingMatch) . '], Jugend [' . implode(', ', $missingYouthMatch) . '].'
				: 'Profis und Jugend können interne Performance Scores speichern.'
		);

		try {
			if (self::tableExists($db, 'spieler') && self::columnExists($db, 'spieler', 'last_performance_score')) {
				$scored = self::countQuery($db, 'spieler', 'last_performance_score > 0', null);
				$total = self::countQuery($db, 'spieler', '1=1', null);
				$items[] = self::item($scored > 0 ? 'ok' : 'info', 'Profis mit Performance-Historie', $scored . ' von ' . $total . ' Spielern haben einen gespeicherten Performance Score.');
			}
			if (self::tableExists($db, 'youthplayer') && self::columnExists($db, 'youthplayer', 'last_performance_score')) {
				$yscored = self::countQuery($db, 'youthplayer', 'last_performance_score > 0', null);
				$ytotal = self::countQuery($db, 'youthplayer', '1=1', null);
				$items[] = self::item($yscored > 0 ? 'ok' : 'info', 'Jugend mit Performance-Historie', $yscored . ' von ' . $ytotal . ' Jugendspielern haben einen gespeicherten Performance Score.');
			}
		} catch (Throwable $e) {
			$items[] = self::item('warn', 'Performance-Historie konnte nicht gezählt werden', $e->getMessage());
		}

		return self::wrapSection('development-system', 'Entwicklung, Stärke, Talent & Jugend', self::severityFromItems($items), $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionForumSystems(DbConnection $db) {
		$items = array();
		$items[] = self::featureStatusItem($db, array(
			'name' => 'Fanforum / Vereinsforum',
			'classes' => array('FanForumService', 'FanForumPlugin', 'FanForumModel'),
			'tables' => array('fanforum_category', 'fanforum_thread', 'fanforum_post', 'fanforum_generation_log', 'fanforum_debug_log'),
			'columns' => array(
				'fanforum_category.enabled',
				'fanforum_thread.team_id',
				'fanforum_thread.category_id',
				'fanforum_thread.last_activity_at',
				'fanforum_post.thread_id',
				'fanforum_post.message',
			),
			'admin_pages' => array('fanforum-admin'),
			'configs' => array('fanforum_enabled', 'fanforum_debug'),
		));
		$items[] = self::featureStatusItem($db, array(
			'name' => 'Transfermarkt-Forum / WoltLab-Brücke',
			'classes' => array(
				'TransferForumModel',
				'TransferForumPermissionsService',
				'WoltLabForumBridgeService',
				'TransferForumPublisherService',
				'TransferForumCreateThreadController',
				'TransferForumReplyController',
				'TransferForumEditPostController',
				'TransferForumDeletePostController',
			),
			'files' => array(
				'classes/models/TransferForumModel.class.php',
				'classes/actions/TransferForumCreateThreadController.class.php',
				'classes/actions/TransferForumReplyController.class.php',
				'classes/actions/TransferForumEditPostController.class.php',
				'classes/actions/TransferForumDeletePostController.class.php',
			),
			'configs' => array(
				'woltlab_forum_api_endpoint',
				'woltlab_forum_api_key',
				'woltlab_forum_transfer_visible_board_ids',
				'woltlab_forum_transfer_create_board_ids',
				'woltlab_forum_transfer_reply_board_ids',
			),
		));
		return self::wrapSection('forums', 'Forum-Systeme', self::severityFromItems($items), $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionModuleInventory() {
		$items = array();
		$base = defined('BASE_FOLDER') ? BASE_FOLDER : dirname(__FILE__) . '/../..';
		$modulesDir = $base . '/modules';
		if (!is_dir($modulesDir)) {
			$items[] = self::item('warn', 'Module-Verzeichnis nicht gefunden', $modulesDir);
			return self::wrapSection('module-inventory', 'Module & Adminseiten', 'warn', $items);
		}
		$moduleCount = 0;
		$parseErrors = 0;
		$missingAdminPages = array();
		$summaryLines = array();
		foreach (glob($modulesDir . '/*/module.xml') as $xmlFile) {
			$moduleCount++;
			$moduleName = basename(dirname($xmlFile));
			$xml = @simplexml_load_file($xmlFile);
			if ($xml === false) {
				$parseErrors++;
				$summaryLines[] = $moduleName . ': module.xml unlesbar';
				continue;
			}
			$pages = self::countXmlNodes($xml, '//page');
			$adminPages = self::countXmlNodes($xml, '//adminpage');
			$actions = self::countXmlNodes($xml, '//action');
			$jobs = self::countXmlNodes($xml, '//job');
			$settings = self::countXmlNodes($xml, '//setting');
			$summaryLines[] = $moduleName . ': Pages ' . $pages . ', Admin ' . $adminPages . ', Actions ' . $actions . ', Jobs ' . $jobs . ', Settings ' . $settings;
			foreach ($xml->xpath('//adminpage') as $ap) {
				$file = trim((string) ($ap['file'] ?? $ap['filename'] ?? ''));
				if ($file === '') {
					continue;
				}
				$file = preg_replace('/\.php$/', '', $file);
				if (!self::adminPageExists($file)) {
					$missingAdminPages[] = $moduleName . ':' . $file;
				}
			}
		}
		$items[] = self::item($parseErrors ? 'error' : 'ok', 'Module gelesen', $moduleCount . ' module.xml Dateien, Parse-Fehler: ' . $parseErrors);
		$items[] = self::item(count($missingAdminPages) ? 'warn' : 'ok', 'Adminseiten aus Modulen',
			count($missingAdminPages)
				? 'Fehlende Adminseiten: ' . implode(', ', array_slice($missingAdminPages, 0, 30)) . (count($missingAdminPages) > 30 ? ' ...' : '')
				: 'Alle referenzierten Adminseiten-Dateien wurden gefunden.');
		$items[] = self::item('info', 'Modul-Inventar', implode("\n", array_slice($summaryLines, 0, 45)) . (count($summaryLines) > 45 ? "\n..." : ''));
		return self::wrapSection('module-inventory', 'Module & Adminseiten', self::severityFromItems($items), $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionJobs() {
		$items = array();
		$path = defined('JOBS_CONFIG_FILE') ? JOBS_CONFIG_FILE : (dirname(__FILE__) . '/../../admin/config/jobs.xml');
		if (!is_readable($path)) {
			$items[] = self::item('error', 'jobs.xml nicht lesbar', $path);
			return self::wrapSection('jobs', 'Cron-Jobs', 'error', $items);
		}
		$xml = @simplexml_load_file($path);
		if ($xml === false) {
			$items[] = self::item('error', 'jobs.xml ungültig', 'XML parse failed');
			return self::wrapSection('jobs', 'Cron-Jobs', 'error', $items);
		}
		$now = (int) getNowAsTimestamp();
		$staleCount = 0;
		$stoppedCount = 0;
		foreach ($xml->job as $job) {
			$id = (string) ($job['id'] ?? '');
			$name = (string) ($job['name_de'] ?? $job['name'] ?? $id);
			$interval = max(1, (int) ($job['interval'] ?? 1));
			$stop = (string) ($job['stop'] ?? '0');
			$lastPing = (int) ($job['last_ping'] ?? 0);
			$error = trim((string) ($job['error'] ?? ''));
			if ($stop === '1') {
				$stoppedCount++;
				$items[] = self::item('warn', 'Job gestoppt: ' . $name, 'ID=' . $id . ' — im Admin unter Jobs starten.');
				continue;
			}
			if (strlen($error)) {
				$items[] = self::item('error', 'Job-Fehler: ' . $name, $error);
			}
			$maxAge = $interval * 120;
			if ($id === 'sim') {
				$maxAge = max(180, $interval * 90);
			}
			if ($lastPing > 0 && ($now - $lastPing) > $maxAge) {
				$staleCount++;
				$hint = ($id === 'sim')
					? ' Nur dieser Job muss jede Minute laufen. Andere Jobs nur, wenn sie im Server-Cron eingetragen sind.'
					: ' Nur relevant, wenn der Job im Hosting-Cron aufgerufen wird (nicht jeder Job läuft bei jedem Install).';
				$items[] = self::item('warn', 'Job ohne frischen Ping: ' . $name,
					'ID=' . $id . ', Intervall=' . $interval . ' Min, letzter Ping vor '
					. (int) floor(($now - $lastPing) / 60) . ' Min (' . date('d.m.Y H:i', $lastPing) . ').' . $hint);
			}
		}
		if (!$stoppedCount && !$staleCount) {
			$items[] = self::item('ok', 'Alle Jobs aktiv', 'Keine gestoppten Jobs, keine stark veralteten Pings.');
		}
		if ($stoppedCount) {
			$items[] = self::item('info', 'Hinweis Sponsoren-Benachrichtigung',
				'Hauptsponsor-Angebote werden u. a. vom Job „Vorstand / Managerentlassung“ (boardmg) ausgelöst — muss laufen.');
		}
		return self::wrapSection('jobs', 'Cron-Jobs', $staleCount || $stoppedCount ? 'warn' : 'ok', $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionSimulation(DbConnection $db) {
		$items = array();
		$now = (int) getNowAsTimestamp();
		try {
			$openDue = self::countQuery($db, 'spiel', "berechnet != '1' AND blocked != '1' AND datum <= %d", $now);
			$blockedDue = self::countQuery($db, 'spiel', "berechnet != '1' AND blocked = '1' AND datum <= %d", $now);
			$stuckKickoff = self::countQuery($db, 'spiel',
				"berechnet != '1' AND (minutes IS NULL OR minutes = 0) AND datum <= %d AND datum >= %d",
				array($now, $now - 7200));
			$items[] = self::item($openDue > 0 ? 'warn' : 'ok', 'Spiel-Queue',
				'Fällig & simulierbar: ' . $openDue . ', blocked: ' . $blockedDue . ', Anpfiff 0\' (2h): ' . $stuckKickoff
				. ' — Details: Admin → Simulation Test');
			if ($blockedDue > 0) {
				$items[] = self::item('warn', 'Hängende Sperren (blocked=1)',
					'Cron sollte diese automatisch lösen. Sonst: Simulation Test → Queue freigeben.');
			}
			$res = @$db->connection->query(
				"SELECT id, spieltyp, datum, minutes, blocked, home_verein, gast_verein FROM spiel"
				. " WHERE berechnet != '1' AND datum <= " . (int) $now
				. ' ORDER BY datum ASC LIMIT 10'
			);
			if ($res && $res->num_rows > 0) {
				$lines = array();
				while ($r = $res->fetch_assoc()) {
					$lines[] = '#' . (int) $r['id'] . ' ' . (string) $r['spieltyp']
						. ' ' . date('d.m. H:i', (int) $r['datum'])
						. ' min=' . (int) $r['minutes'] . ' blk=' . (string) $r['blocked']
						. ' ' . (int) $r['home_verein'] . ':' . (int) $r['gast_verein'];
				}
				$res->free();
				$items[] = self::item('info', 'Offene Spiele (max. 10)', implode("\n", $lines));
			}
		} catch (Throwable $e) {
			$items[] = self::item('error', 'Simulation-Check fehlgeschlagen', $e->getMessage());
		}
		$severity = 'ok';
		foreach ($items as $it) {
			if (($it['level'] ?? '') === 'error') {
				$severity = 'error';
				break;
			}
			if (($it['level'] ?? '') === 'warn') {
				$severity = 'warn';
			}
		}
		return self::wrapSection('simulation', 'Simulation', $severity, $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionLogs() {
		$items = array();
		$base = defined('BASE_FOLDER') ? BASE_FOLDER : dirname(__FILE__) . '/../..';
		$paths = array(
			'Frontend-Fehler' => $base . '/generated/live_page_errors.log',
			'Sim-Fehler (Match)' => $base . '/generated/sim_match_errors.log',
			'Job sim' => $base . '/admin/logs/job-sim.log',
			'Job boardmg' => $base . '/admin/logs/job-boardmg.log',
		);
		$foundError = false;
		foreach ($paths as $label => $path) {
			if (!is_readable($path)) {
				$items[] = self::item('info', $label, 'Keine Logdatei: ' . $path);
				continue;
			}
			$tail = self::tailFile($path, 40);
			$simErrors = array();
			foreach ($tail as $line) {
				if (stripos($line, '[sim-error]') !== false || stripos($line, 'ERROR') !== false || stripos($line, 'Fatal') !== false) {
					$simErrors[] = $line;
				}
			}
			if (count($simErrors)) {
				$foundError = true;
				$items[] = self::item('error', $label . ' — Fehlerzeilen', implode("\n", array_slice($simErrors, -8)));
			} else {
				$items[] = self::item('ok', $label, 'Letzte ' . count($tail) . ' Zeilen ohne ERROR/[sim-error].');
			}
		}
		return self::wrapSection('logs', 'PHP- & Job-Logs', $foundError ? 'error' : 'ok', $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionPhpEnvironment() {
		$items = array();
		$items[] = self::item('info', 'PHP-Version', PHP_VERSION);
		$items[] = self::item('info', 'memory_limit', (string) ini_get('memory_limit'));
		$items[] = self::item('info', 'max_execution_time', (string) ini_get('max_execution_time'));
		$base = defined('BASE_FOLDER') ? BASE_FOLDER : dirname(__FILE__) . '/../..';
		$coreClasses = array(
			'MatchSimulationExecutor' => $base . '/classes/MatchSimulationExecutor.class.php',
			'FormationDataService' => $base . '/classes/services/FormationDataService.class.php',
		);
		foreach ($coreClasses as $class => $path) {
			$loadError = '';
			if (!class_exists($class, true) && is_readable($path)) {
				try {
					require_once $path;
				} catch (Throwable $e) {
					$loadError = $e->getMessage();
				}
			}
			$loaded = class_exists($class, true);
			$items[] = self::item(
				$loaded ? 'ok' : 'warn',
				$class,
				$loaded ? 'Datei vorhanden und ladbar.' : ('Datei fehlt oder Parse-Fehler: ' . $path . ($loadError !== '' ? ' — ' . $loadError : ''))
			);
		}
		return self::wrapSection('php', 'PHP-Umgebung', 'ok', $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionLiveticker(DbConnection $db, $matchLimit) {
		$items = array();
		if (!class_exists('LivetickerCoverageDiagnosticsService', false)) {
			$path = dirname(__FILE__) . '/LivetickerCoverageDiagnosticsService.class.php';
			if (is_readable($path)) {
				require_once $path;
			}
		}
		if (!class_exists('LivetickerCoverageDiagnosticsService')) {
			$items[] = self::item('warn', 'Liveticker-Diagnose', 'Service nicht verfügbar.');
			return self::wrapSection('liveticker', 'Liveticker-Texte', 'warn', $items);
		}
		try {
			$report = LivetickerCoverageDiagnosticsService::buildReport($db, $matchLimit, 0);
			$never = isset($report['never_triggered_actions']) ? (array) $report['never_triggered_actions'] : array();
			$mislabeled = isset($report['mislabeled_db_actions']) ? count((array) $report['mislabeled_db_actions']) : 0;
			$items[] = self::item('info', 'Auswertungsbasis',
				'Letzte ' . (int) ($report['match_count'] ?? $matchLimit) . ' berechnete Spiele. '
				. 'Details: Admin → Simulation Test → Liveticker-Abdeckung.');
			if ($mislabeled > 0) {
				$items[] = self::item('warn', 'Falsch benannte DB-Aktionen', (string) $mislabeled
					. ' Einträge in spiel_text (Import-Altlasten) — können Trigger verhindern.');
			}
			if (count($never) > 0) {
				$top = array_slice($never, 0, 12);
				$lines = array();
				foreach ($top as $row) {
					if (is_array($row)) {
						$lines[] = (string) ($row['aktion'] ?? $row['action'] ?? '?')
							. ' (' . (int) ($row['text_count'] ?? 0) . ' Texte in DB, 0× ausgelöst)';
					}
				}
				$items[] = self::item('warn', 'Aktionen nie ausgelöst (Top 12)',
					implode("\n", $lines) . (count($never) > 12 ? "\n… und " . (count($never) - 12) . ' weitere' : ''));
			} else {
				$items[] = self::item('ok', 'Liveticker-Aktionen', 'Keine komplett ungenutzten Aktionen im Zeitraum.');
			}
		} catch (Throwable $e) {
			$items[] = self::item('error', 'Liveticker-Check', $e->getMessage());
		}
		$severity = 'ok';
		foreach ($items as $it) {
			if (($it['level'] ?? '') === 'error') {
				$severity = 'error';
			} elseif (($it['level'] ?? '') === 'warn' && $severity !== 'error') {
				$severity = 'warn';
			}
		}
		return self::wrapSection('liveticker', 'Liveticker-Texte', $severity, $items);
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionSponsors(WebSoccer $websoccer, DbConnection $db, $clubIdFilter) {
		$items = array();
		if (!class_exists('SponsorsDataService')) {
			$items[] = self::item('warn', 'SponsorsDataService', 'Nicht verfügbar.');
			return self::wrapSection('sponsors', 'Hauptsponsor & Angebote', 'warn', $items);
		}
		SponsorsDataService::normalizeSponsorOfferData($db);
		$earliestLeague = max(1, (int) getConfig('sponsor_earliest_matchday', 3));
		$earliestCup = max(1, (int) getConfig('sponsor_earliest_cup_matches', 1));
		$items[] = self::item('info', 'Konfiguration',
			'sponsor_earliest_matchday=' . $earliestLeague
			. ' (letzter abgeschlossener Ligaspieltag), sponsor_earliest_cup_matches=' . $earliestCup);

		$where = "status = '1' AND nationalteam = '0' AND user_id IS NOT NULL AND user_id > 0";
		$params = array();
		if ($clubIdFilter > 0) {
			$where .= ' AND id = %d';
			$params[] = $clubIdFilter;
		}
		$res = $db->querySelect('id, name, liga_id, sponsor_id, sponsor_spiele', 'verein', $where, $params, $clubIdFilter > 0 ? 1 : 80);
		$blocked = 0;
		$eligible = 0;
		while ($club = $res->fetch_array()) {
			$clubId = (int) ($club['id'] ?? 0);
			$lastDone = class_exists('MatchesDataService')
				? (int) MatchesDataService::getMatchdayNumberOfTeam($websoccer, $db, $clubId) : 0;
			$maxScheduled = self::getMaxScheduledLeagueMatchday($db, $clubId);
			$can = SponsorsDataService::canClubChooseSponsors($websoccer, $db, $clubId);
			if ($can) {
				$eligible++;
			} else {
				$blocked++;
			}
			if ($clubIdFilter > 0 || $blocked <= 5) {
				$detail = self::buildSponsorClubDetail($websoccer, $db, $clubId, $club, $lastDone, $maxScheduled, $earliestLeague, $earliestCup, $can);
				$items[] = self::item($can ? 'ok' : 'warn',
					($club['name'] ?? 'Verein') . ' (#' . $clubId . ')',
					$detail);
			}
		}
		$res->free();
		if ($clubIdFilter < 1 && $blocked > 5) {
			$items[] = self::item('info', 'Weitere Vereine',
				$blocked . ' Vereine noch ohne Freischaltung (Filter: ?club_id=ID).');
		}
		$mainSponsors = self::countQuery($db, 'sponsor',
			"(sponsor_type = 'main' OR sponsor_type = '' OR sponsor_type IS NULL)",
			null);
		$typedMain = self::countQuery($db, 'sponsor', "sponsor_type = 'main'", null);
		$legacyEmpty = self::countQuery($db, 'sponsor',
			"(sponsor_type = '' OR sponsor_type IS NULL)",
			null);
		$sideType = self::countQuery($db, 'sponsor', "sponsor_type = 'side'", null);
		$globalMain = self::countQuery($db, 'sponsor',
			"(sponsor_type = 'main' OR sponsor_type = '' OR sponsor_type IS NULL) AND is_global = 1",
			null);
		$items[] = self::item($mainSponsors > 0 ? 'ok' : 'error', 'Sponsor-Stammdaten (main)',
			$mainSponsors . ' gesamt (main: ' . $typedMain . ', leer: ' . $legacyEmpty . ', side: ' . $sideType . ', global: ' . $globalMain . ').');
		if ($clubIdFilter > 0) {
			$offers = SponsorsDataService::getSponsorOffersForSlot($websoccer, $db, $clubIdFilter, 'main');
			$items[] = self::item(count($offers) > 0 ? 'ok' : 'warn',
				'Test Hauptsponsor-Angebote Verein #' . $clubIdFilter,
				count($offers) . ' Angebote nach aktueller Abfrage-Logik.');
		} else {
			$sampleLeagues = array(1, 2, 3, 7, 11);
			$ligaLines = array();
			foreach ($sampleLeagues as $lid) {
				$c = self::countQuery($db, 'sponsor',
					"(sponsor_type = 'main' OR sponsor_type = '' OR sponsor_type IS NULL) AND (liga_id = 0 OR liga_id = %d)",
					$lid);
				$ligaLines[] = 'Liga ' . $lid . ': ' . $c . ' main-Treffer';
			}
			$items[] = self::item('info', 'Main-Sponsoren pro Liga (Stichprobe)', implode("\n", $ligaLines));
		}
		if (class_exists('StadiumSponsoringDataService', true)) {
			StadiumSponsoringDataService::ensureSchema($db);
			$namingPool = self::countQuery($db, 'stadium_sponsor', "sponsor_type = 'naming' AND active = 1", null);
			$adsPool = self::countQuery($db, 'stadium_sponsor', "sponsor_type = 'ads' AND active = 1", null);
			$items[] = self::item(
				($namingPool > 0 && $adsPool > 0) ? 'ok' : 'warn',
				'Stadion-Sponsor-Pool (Banden/Naming)',
				'Naming: ' . $namingPool . ', Banden (ads): ' . $adsPool
				. ' — Angebote erscheinen beim Besuch der Stadion-Seite (Kapazität ≥ '
				. (int) StadiumSponsoringDataService::adsMinCapacity() . ' für Banden).'
			);
			if ($namingPool < 1 || $adsPool < 1) {
				$items[] = self::item('info', 'boardmg-Job',
					'Cron-Job boardmg (Vorstand) sollte laufen; ohne Pool werden Standard-Sponsoren beim ersten Stadion-Besuch angelegt.');
			}
		}
		return self::wrapSection('sponsors', 'Hauptsponsor & Angebote', $mainSponsors < 1 ? 'error' : 'ok', $items);
	}

	private static function buildSponsorClubDetail(WebSoccer $websoccer, DbConnection $db, $clubId, array $club, $lastDone, $maxScheduled, $earliestLeague, $earliestCup, $can) {
		$lines = array();
		$lines[] = 'Letzter abgeschlossener Ligaspieltag (berechnet=1): ' . $lastDone;
		$lines[] = 'Höchster geplanter Ligaspieltag in DB: ' . $maxScheduled;
		$lines[] = 'Freischaltung: ' . ($can ? 'JA' : 'NEIN')
			. ' (benötigt Ligaspieltag ≥ ' . $earliestLeague . ' abgeschlossen ODER ' . $earliestCup . ' Pokalspiel(e))';
		if (!$can) {
			if ($lastDone < $earliestLeague) {
				$lines[] = '→ Noch ' . ($earliestLeague - $lastDone) . ' abgeschlossene Spieltag(e) bis zur Freischaltung.';
			}
			if ($maxScheduled >= $earliestLeague && $lastDone < $earliestLeague) {
				$lines[] = '→ Spieltag ' . $maxScheduled . ' ist terminiert, zählt aber erst nach Abpfiff (berechnet=1).';
			}
		}
		$legacy = (int) ($club['sponsor_id'] ?? 0);
		$legacyGames = (int) ($club['sponsor_spiele'] ?? 0);
		if ($legacy > 0 && $legacyGames > 0) {
			$lines[] = 'Legacy-Sponsor aktiv (verein.sponsor_id=' . $legacy . ', Restspiele=' . $legacyGames . ').';
		}
		$contracts = SponsorsDataService::getActiveContractsByClubId($websoccer, $db, $clubId);
		$lines[] = 'Aktive Verträge (club_sponsor_contract): ' . count($contracts);
		$open = SponsorsDataService::getOpenSlotsByClubId($db, $clubId);
		$offerTotal = 0;
		foreach ((array) $open as $slotType => $indices) {
			$offers = SponsorsDataService::getSponsorOffersForSlot($websoccer, $db, $clubId, (string) $slotType);
			$c = is_array($offers) ? count($offers) : 0;
			$offerTotal += $c * count((array) $indices);
			if ($slotType === 'main' && count((array) $indices) > 0) {
				$lines[] = 'Hauptsponsor-Slot offen: ' . count((array) $indices) . ' Platz/Plätze, ' . $c . ' Angebote in Liga ' . (int) ($club['liga_id'] ?? 0);
				if ($c < 1 && $can) {
					$lines[] = '→ Keine passenden Sponsoren (liga_id/is_global/country_code; land vs. DE — nach Update SponsorsDataService.class.php deployen).';
				}
			}
		}
		if ($can && $offerTotal < 1 && !count($contracts)) {
			$lines[] = '→ Freigeschaltet, aber keine Angebote — sponsor-Tabelle oder Liga-Zuordnung prüfen.';
		}
		return implode("\n", $lines);
	}

	private static function getMaxScheduledLeagueMatchday(DbConnection $db, $clubId) {
		$clubId = (int) $clubId;
		$res = $db->querySelect(
			'MAX(spieltag) AS mx',
			'spiel',
			"spieltyp = 'Ligaspiel' AND (home_verein = %d OR gast_verein = %d)",
			array($clubId, $clubId),
			1
		);
		$row = $res ? $res->fetch_array() : null;
		if ($res) {
			$res->free();
		}
		return $row ? (int) ($row['mx'] ?? 0) : 0;
	}

	/**
	 * @return array<string,mixed>
	 */
	private static function sectionConfigHints() {
		$items = array();
		$checks = array(
			'sim_interval' => '7',
			'sim_batch_cap_enabled' => '0',
			'sim_skip_kickoff_delay' => '1',
			'sponsor_earliest_matchday' => '3',
			'webjobexecution_enabled' => '1',
		);
		foreach ($checks as $key => $recommended) {
			$cur = (string) getConfig($key, $recommended);
			if ($cur !== (string) $recommended) {
				$items[] = self::item('info', $key, 'Aktuell: ' . $cur . ' — empfohlen: ' . $recommended);
			}
		}
		if (!count($items)) {
			$items[] = self::item('ok', 'Kern-Einstellungen', 'Simulations- und Sponsor-Basiseinstellungen wie empfohlen.');
		}
		return self::wrapSection('config', 'Einstellungen (Hinweise)', 'ok', $items);
	}

	private static function featureStatusItem(DbConnection $db, array $feature) {
		$name = (string) ($feature['name'] ?? 'Feature');
		$ok = array();
		$warn = array();
		$error = array();
		foreach ((array) ($feature['classes'] ?? array()) as $class) {
			$class = (string) $class;
			$loadError = '';
			if (self::classAvailable($class, $loadError)) {
				$ok[] = 'Klasse ' . $class;
			} else {
				$error[] = 'Klasse ' . $class . ' fehlt oder laedt nicht' . ($loadError !== '' ? ': ' . $loadError : '');
			}
		}
		foreach ((array) ($feature['files'] ?? array()) as $file) {
			$file = (string) $file;
			if (self::projectFileExists($file)) {
				$ok[] = 'Datei ' . $file;
			} else {
				$error[] = 'Datei fehlt: ' . $file;
			}
		}
		foreach ((array) ($feature['tables'] ?? array()) as $table) {
			$table = (string) $table;
			if (self::tableExists($db, $table)) {
				$ok[] = 'Tabelle ' . $table;
			} else {
				$error[] = 'Tabelle fehlt: ' . $table;
			}
		}
		foreach ((array) ($feature['columns'] ?? array()) as $columnRef) {
			$parts = explode('.', (string) $columnRef, 2);
			if (count($parts) !== 2) {
				$warn[] = 'Ungueltige Spaltenreferenz in Diagnose: ' . (string) $columnRef;
				continue;
			}
			if (!self::tableExists($db, $parts[0])) {
				$error[] = 'Spalte nicht pruefbar, Tabelle fehlt: ' . (string) $columnRef;
				continue;
			}
			if (self::columnExists($db, $parts[0], $parts[1])) {
				$ok[] = 'Spalte ' . (string) $columnRef;
			} else {
				$warn[] = 'Spalte fehlt/Upgrade noetig: ' . (string) $columnRef;
			}
		}
		foreach ((array) ($feature['admin_pages'] ?? array()) as $page) {
			$page = (string) $page;
			if (self::adminPageExists($page)) {
				$ok[] = 'Adminseite ' . $page;
			} else {
				$warn[] = 'Adminseite fehlt: ' . $page;
			}
		}
		$configLines = array();
		foreach ((array) ($feature['configs'] ?? array()) as $key) {
			$key = (string) $key;
			$value = '';
			try {
				$value = (string) getConfig($key, '');
			} catch (Throwable $e) {
				$warn[] = 'Config nicht lesbar: ' . $key . ' (' . $e->getMessage() . ')';
				continue;
			}
			$configLines[] = $key . '=' . ($value === '' ? '[leer/nicht gesetzt]' : $value);
		}
		if (count($configLines)) {
			$ok[] = 'Config: ' . implode(', ', $configLines);
		}
		$level = count($error) ? 'error' : (count($warn) ? 'warn' : 'ok');
		$detail = array();
		if (count($error)) {
			$detail[] = 'Fehler:';
			foreach ($error as $line) {
				$detail[] = '- ' . $line;
			}
		}
		if (count($warn)) {
			$detail[] = 'Anpassen/pruefen:';
			foreach ($warn as $line) {
				$detail[] = '- ' . $line;
			}
		}
		if (count($ok)) {
			$detail[] = 'OK:';
			foreach (array_slice($ok, 0, 18) as $line) {
				$detail[] = '- ' . $line;
			}
			if (count($ok) > 18) {
				$detail[] = '- ... ' . (count($ok) - 18) . ' weitere Checks OK';
			}
		}
		return self::item($level, $name, implode("\n", $detail));
	}

	private static function severityFromItems(array $items) {
		$severity = 'ok';
		foreach ($items as $it) {
			$level = (string) ($it['level'] ?? 'info');
			if ($level === 'error') {
				return 'error';
			}
			if ($level === 'warn') {
				$severity = 'warn';
			}
		}
		return $severity;
	}

	private static function classAvailable($class, &$loadError = '') {
		$loadError = '';
		try {
			return class_exists((string) $class, true);
		} catch (Throwable $e) {
			$loadError = $e->getMessage();
			return false;
		}
	}

	private static function projectFileExists($relativePath) {
		$base = defined('BASE_FOLDER') ? BASE_FOLDER : dirname(__FILE__) . '/../..';
		$relativePath = str_replace('\\', '/', (string) $relativePath);
		return is_readable(rtrim($base, '/\\') . '/' . ltrim($relativePath, '/'));
	}

	private static function adminPageExists($page) {
		$page = preg_replace('/\.php$/', '', (string) $page);
		$base = defined('BASE_FOLDER') ? BASE_FOLDER : dirname(__FILE__) . '/../..';
		return is_readable(rtrim($base, '/\\') . '/admin/pages/' . $page . '.php');
	}

	private static function tableExists(DbConnection $db, $table) {
		$table = (string) $table;
		if (!preg_match('/^[A-Za-z0-9_]+$/', $table)) {
			return false;
		}
		try {
			$escaped = $db->connection->real_escape_string($table);
			$res = @$db->connection->query(
				"SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '" . $escaped . "'"
			);
			$row = $res ? $res->fetch_assoc() : null;
			if ($res) {
				$res->free();
			}
			return $row && (int) ($row['c'] ?? 0) > 0;
		} catch (Throwable $e) {
			return false;
		}
	}

	private static function columnExists(DbConnection $db, $table, $column) {
		$table = (string) $table;
		$column = (string) $column;
		if (!preg_match('/^[A-Za-z0-9_]+$/', $table) || !preg_match('/^[A-Za-z0-9_]+$/', $column)) {
			return false;
		}
		try {
			$escapedTable = $db->connection->real_escape_string($table);
			$escapedColumn = $db->connection->real_escape_string($column);
			$res = @$db->connection->query(
				"SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE()"
				. " AND TABLE_NAME = '" . $escapedTable . "' AND COLUMN_NAME = '" . $escapedColumn . "'"
			);
			$row = $res ? $res->fetch_assoc() : null;
			if ($res) {
				$res->free();
			}
			return $row && (int) ($row['c'] ?? 0) > 0;
		} catch (Throwable $e) {
			return false;
		}
	}

	private static function missingColumns(DbConnection $db, $table, array $columns) {
		$missing = array();
		if (!self::tableExists($db, $table)) {
			return array('Tabelle fehlt: ' . $table);
		}
		foreach ($columns as $column) {
			if (!self::columnExists($db, $table, (string) $column)) {
				$missing[] = (string) $column;
			}
		}
		return $missing;
	}

	private static function countXmlNodes(SimpleXMLElement $xml, $path) {
		$nodes = $xml->xpath($path);
		return is_array($nodes) ? count($nodes) : 0;
	}

	/**
	 * @param string $level ok|warn|error|info
	 * @return array<string,string>
	 */
	private static function item($level, $title, $detail) {
		return array(
			'level' => $level,
			'title' => (string) $title,
			'detail' => (string) $detail,
		);
	}

	/**
	 * @param array<int,array<string,string>> $items
	 * @return array<string,mixed>
	 */
	private static function wrapSection($id, $title, $severity, array $items) {
		return array(
			'id' => $id,
			'title' => $title,
			'severity' => $severity,
			'items' => $items,
		);
	}

	private static function countQuery(DbConnection $db, $table, $where, $params) {
		$res = $db->querySelect('COUNT(*) AS hits', $table, $where, $params, 1);
		$row = $res ? $res->fetch_array() : null;
		if ($res) {
			$res->free();
		}
		return (int) ($row['hits'] ?? 0);
	}

	/**
	 * @return array<int,string>
	 */
	private static function tailFile($path, $lines = 30) {
		$lines = max(5, (int) $lines);
		if (!is_readable($path)) {
			return array();
		}
		$content = @file($path, FILE_IGNORE_NEW_LINES);
		if (!is_array($content)) {
			return array();
		}
		return array_slice($content, -$lines);
	}
}
