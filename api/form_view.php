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
    'table'   => null,
];

function app_base_url() {
    $scheme = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
    $host = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '';
    return $host ? ($scheme . '://' . $host) : '';
}

function material_line_to_row($line) {
    $parts = array_map('trim', explode('|', $line));

    $number = '';
    $name = isset($parts[0]) ? $parts[0] : '';
    if (preg_match('/^(\d+)[\.\)]?\s*(.*)$/u', $name, $m)) {
        $number = $m[1];
        $name = trim($m[2]);
    }

    $unit = isset($parts[1]) ? $parts[1] : '';
    $price = isset($parts[2]) ? $parts[2] : '';
    $category = isset($parts[3]) ? str_replace('категория:', '', $parts[3]) : '';
    $category = trim($category);

    return [
        'number' => $number,
        'name' => [
            'text' => $name,
            // Если на сайте есть точный URL карточки/строки, лучше отдать его здесь.
            'href' => app_base_url() . '/?search=' . rawurlencode($name),
        ],
        'unit' => $unit,
        'price' => $price,
        'category' => $category,
    ];
}

function build_materials_table($lines) {
    $rows = [];
    foreach ($lines as $line) {
        $rows[] = material_line_to_row($line);
    }

    return [
        'columns' => [
            ['key' => 'number', 'title' => '№', 'width' => 60, 'align' => 'center'],
            ['key' => 'name', 'title' => 'Наименование', 'width' => 520, 'align' => 'left'],
            ['key' => 'unit', 'title' => 'Ед.', 'width' => 110, 'align' => 'center'],
            ['key' => 'price', 'title' => 'Цена', 'width' => 140, 'align' => 'center'],
            ['key' => 'category', 'title' => 'Категория', 'width' => 150, 'align' => 'center'],
        ],
        'rows' => $rows,
    ];
}

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

    if ($result['table'] === null && !empty($result['lines'])) {
        $firstLine = isset($result['lines'][0]) ? $result['lines'][0] : '';
        if (strpos($firstLine, '|') !== false) {
            $result['table'] = build_materials_table($result['lines']);
        }
    }

    echo json_encode($result, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

} catch (Exception $e) {
    echo json_encode([
        'success' => false,
        'error'   => 'DB error: ' . $e->getMessage(),
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}
