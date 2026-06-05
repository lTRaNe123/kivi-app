<?php
// /var/www/html/api/form_view.php

header('Content-Type: application/json; charset=utf-8');

require_once __DIR__ . '/../core/session.php';
require_once __DIR__ . '/../core/db.php';

// Проверяем авторизацию
if (!isLoggedOn() || empty($userdata['uid'])) {
    echo json_encode([
        'success' => false,
        'error'   => 'Not authorized',
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

$code = isset($_GET['code']) ? trim($_GET['code']) : '';
$code = strtolower($code);

if ($code === '') {
    echo json_encode([
        'success' => false,
        'error'   => 'Не указан параметр code',
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

// Заготовка ответа
$result = [
    'success' => true,
    'title'   => '',
    'header'  => '',
    'lines'   => [],
];

// ВНИМАНИЕ:
// Здесь я использую только таблицу users,
// потому что других схем у нас в переписке нет.
// Ты сможешь потом доработать каждый case и
// сформировать строки так, как тебе нужно.

try {
    switch ($code) {
        // КНИГА №10 (условный вариант, сейчас просто список личного состава)
        case 'f10':
        case 'book10':
            $result['title']  = 'Книга №10';
            $result['header'] = 'Условный список военнослужащих (черновой вариант)';

            $sql = "
                SELECT snid, username, name, otec, battery, position
                FROM users
                ORDER BY battery, snid, username
            ";
            $stmt = $link->query($sql);

            $i = 1;
            while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
                $snid     = $row['snid'];
                $fioLogin = trim($row['username'] . ' ' . $row['name'] . ' ' . $row['otec']);
                $battery  = $row['battery'];
                $pos      = $row['position'];

                $line = sprintf(
                    '%3d. [%s] %s — %s',
                    $i,
                    $battery,
                    $fioLogin,
                    $pos
                );
                $result['lines'][] = $line;
                $i++;
            }
            break;

        // Вечерняя поверка
        case 'evening':
        case 'vecher':
            $result['title']  = 'Версия 0.2';
            $result['header'] = 'Вечерняя поверка (упрощённый вид)';

            $sql = "
                SELECT snid, username, name, otec, battery
                FROM users
                ORDER BY battery, snid, username
            ";
            $stmt = $link->query($sql);

            $i = 1;
            while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
                $snid = $row['snid'];
                $fio  = trim($row['username'] . ' ' . $row['name'] . ' ' . $row['otec']);
                $bat  = $row['battery'];

                // Здесь можно добавить даты/отметки, если есть отдельная таблица.
                // Сейчас просто выводим список строк.
                $line = sprintf(
                    '%3d. [%s] %s (№ по списку: %s)',
                    $i,
                    $bat,
                    $fio,
                    $snid
                );
                $result['lines'][] = $line;
                $i++;
            }
            break;

        // Спальное расположение (упрощённый вывод на основе users)
        case 'sleep':
        case 'spal':
            $result['title']  = 'Версия 0.2';
            $result['header'] = 'Спальное расположение (условный вариант)';

            $sql = "
                SELECT snid, username, name, otec, battery
                FROM users
                ORDER BY battery, snid, username
            ";
            $stmt = $link->query($sql);

            while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
                $place = $row['snid']; // здесь можно заменить на реальный номер койки, если будет таблица
                $fio   = trim($row['username'] . ' ' . $row['name'] . ' ' . $row['otec']);
                $bat   = $row['battery'];

                $line = sprintf(
                    'Койка %s — [%s] %s',
                    $place,
                    $bat,
                    $fio
                );
                $result['lines'][] = $line;
            }
            break;

        // Штатка
        case 'shtatka':
        case 'shtat':
            $result['title']  = 'Версия 0.2';
            $result['header'] = 'Штатка (штатная / фактическая должности)';

            $sql = "
                SELECT snid, position, rank_shtat, rank_fact, username, name, otec, battery
                FROM users
                ORDER BY battery, snid, username
            ";
            $stmt = $link->query($sql);

            $i = 1;
            while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
                $fio = trim($row['username'] . ' ' . $row['name'] . ' ' . $row['otec']);
                $bat = $row['battery'];

                $line = sprintf(
                    '%3d. [%s] %s — %s | по штату: %s, фактически: %s',
                    $i,
                    $bat,
                    $fio,
                    $row['position'],
                    $row['rank_shtat'],
                    $row['rank_fact']
                );
                $result['lines'][] = $line;
                $i++;
            }
            break;

        default:
            echo json_encode([
                'success' => false,
                'error'   => 'Неизвестный code: ' . $code,
            ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
            exit;
    }

    echo json_encode($result, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

} catch (Exception $e) {
    echo json_encode([
        'success' => false,
        'error'   => 'DB error: ' . $e->getMessage(),
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}
