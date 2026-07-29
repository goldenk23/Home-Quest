const MAX_COORD = 10_000;
const MAX_ENTITIES = 1_000;
const MAX_POINTS = 4_000;
const SIDES = new Set(['top', 'right', 'bottom', 'left']);
const SHAPES = new Set(['line', 'polygon']);
const FLOORING = new Set(['wood', 'Wood', 'marble', 'Marble', 'tile', 'Tile', 'garden', 'grass', 'Garden']);
const FURNITURE = new Set([
  'double_bed', 'circular_bed', 'bed_with_side_table', 'single_bed',
  'sofa', 'Sofa_Set_with_Centre_Table', 'sofa_set_with_centre_table', 'single_sofa',
  'Chair', 'chair', 'coffee_table', 'dining_table_4_seat', 'dining_table_6_seat',
  'dining_table_8_seat', 'Table_Chair_Set', 'table_chair_set', 'Study_Table_Chair',
  'study_table_chair', 'desk', 'wardrobe', 'Wardrobe', 'Standing_Cabinet',
  'standing_cabinet', 'tv', 'TV', 'fridge', 'Fridge', 'stove', 'sink',
  'kitchen_platform', 'kitchen_platform_2', 'kitchen_platform_3', 'kitchen_platform_4',
  'Toilet', 'toilet', 'Bath Tub', 'bathtub', 'Bath_Tub', 'shower', 'Wash_Basin',
  'Wash_basin', 'wash_basin', 'singlehand_door', 'doublehand_door',
]);

const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = (value, path, errors, min = -MAX_COORD, max = MAX_COORD) => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) {
    errors.push(`${path} must be a finite number from ${min} to ${max}`);
    return false;
  }
  return true;
};
const string = (value, path, errors, max = 200) => {
  if (typeof value !== 'string' || !value.trim() || value.length > max) {
    errors.push(`${path} must be a non-empty string of at most ${max} characters`);
    return false;
  }
  return true;
};
const collection = (value, path, errors, max) => {
  if (!Array.isArray(value)) {
    errors.push(`${path} must be an array`);
    return [];
  }
  if (value.length > max) errors.push(`${path} has more than ${max} items`);
  return value;
};

function boundedTree(root, errors) {
  let nodes = 0;
  const visit = (value, path, depth) => {
    if (++nodes > 15_000) return errors.push('layout is too complex');
    if (depth > 10) return errors.push(`${path} is nested too deeply`);
    if (typeof value === 'string' && value.length > 2_000) errors.push(`${path} exceeds 2000 characters`);
    if (typeof value === 'number' && (!Number.isFinite(value) || Math.abs(value) > 1_000_000)) errors.push(`${path} is not a bounded finite number`);
    if (Array.isArray(value)) {
      if (value.length > 4_000) errors.push(`${path} array is too large`);
      value.forEach((item, index) => visit(item, `${path}[${index}]`, depth + 1));
    } else if (object(value)) {
      const entries = Object.entries(value);
      if (entries.length > 100) errors.push(`${path} has too many fields`);
      for (const [key, item] of entries) {
        if (key.length > 64) errors.push(`${path} has an overlong field name`);
        visit(item, `${path}.${key}`, depth + 1);
      }
    }
  };
  visit(root, 'layout', 0);
}

function validateFlooring(value, path, errors) {
  if (!object(value) || typeof value.has_flooring !== 'boolean') {
    errors.push(`${path} must contain boolean has_flooring`);
    return;
  }
  if (value.has_flooring && !FLOORING.has(value.flooring_type)) {
    errors.push(`${path}.flooring_type is unsupported`);
  }
  if (value.image_path != null && (typeof value.image_path !== 'string' || value.image_path.length > 300)) {
    errors.push(`${path}.image_path is invalid`);
  }
}

function point(value, path, errors, width, height) {
  if (!Array.isArray(value) || value.length !== 2) {
    errors.push(`${path} must be [x, y]`);
    return false;
  }
  return finite(value[0], `${path}[0]`, errors, 0, width) && finite(value[1], `${path}[1]`, errors, 0, height);
}

function distanceToSegment(px, py, x0, y0, x1, y1) {
  const dx = x1 - x0;
  const dy = y1 - y0;
  const t = Math.max(0, Math.min(1, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(px - (x0 + t * dx), py - (y0 + t * dy));
}
export function validateLayout(layout) {
  const errors = [];
  if (!object(layout)) return { ok: false, errors: ['layout must be a JSON object'] };
  boundedTree(layout, errors);
  if (layout.version !== '1.0') errors.push('version must be "1.0"');
  const metadata = object(layout.metadata) ? layout.metadata : null;
  if (!metadata) errors.push('metadata must be an object');
  const width = metadata?.canvas_width;
  const height = metadata?.canvas_height;
  if (metadata) {
    string(metadata.project_name, 'metadata.project_name', errors, 120);
    if (metadata.description != null && (typeof metadata.description !== 'string' || metadata.description.length > 500)) errors.push('metadata.description is invalid');
    if (metadata.unit !== 'ft') errors.push('metadata.unit must be "ft"');
    if (metadata.unit_scale !== 1) errors.push('metadata.unit_scale must be 1');
    if (metadata.grid_spacing !== 20) errors.push('metadata.grid_spacing must be 20 (20 canvas pixels = 1 ft)');
    if (metadata.zoom_level !== 1) errors.push('metadata.zoom_level must be 1');
    finite(width, 'metadata.canvas_width', errors, 100, 5_000);
    finite(height, 'metadata.canvas_height', errors, 100, 5_000);
    finite(metadata.wall_height_cm, 'metadata.wall_height_cm', errors, 100, 1_000);
  }

  const rooms = collection(layout.rooms, 'rooms', errors, 100);
  const furniture = collection(layout.furniture, 'furniture', errors, 500);
  const shapes = collection(layout.shapes, 'shapes', errors, 200);
  const texts = collection(layout.text, 'text', errors, 200);
  if (rooms.length + furniture.length + shapes.length + texts.length > MAX_ENTITIES) errors.push(`layout exceeds ${MAX_ENTITIES} entities`);
  if (!Number.isFinite(width) || !Number.isFinite(height)) return { ok: false, errors: [...new Set(errors)].slice(0, 40) };

  const ids = new Set();
  const roomTags = new Set();
  const polygonTags = new Set();
  const gaps = [];
  const addId = (item, path) => {
    if (!object(item)) return errors.push(`${path} must be an object`);
    if (string(item.id, `${path}.id`, errors, 100)) {
      if (ids.has(item.id)) errors.push(`${path}.id must be unique`);
      ids.add(item.id);
    }
  };

  rooms.forEach((room, index) => {
    const path = `rooms[${index}]`;
    addId(room, path);
    if (!object(room)) return;
    string(room.name, `${path}.name`, errors, 120);
    if (string(room.group_tag, `${path}.group_tag`, errors, 100)) {
      if (!/^room_group_[A-Za-z0-9_-]+$/.test(room.group_tag)) errors.push(`${path}.group_tag must start with room_group_`);
      if (roomTags.has(room.group_tag)) errors.push(`${path}.group_tag must be unique`);
      roomTags.add(room.group_tag);
    }
    const validRect = finite(room.x0, `${path}.x0`, errors, 0, width) & finite(room.y0, `${path}.y0`, errors, 0, height) &
      finite(room.x1, `${path}.x1`, errors, 0, width) & finite(room.y1, `${path}.y1`, errors, 0, height);
    if (validRect && (room.x1 <= room.x0 || room.y1 <= room.y0)) errors.push(`${path} must be a positive nonzero rectangle`);
    if (room.width != null && Math.abs(room.width - (room.x1 - room.x0)) > 0.01) errors.push(`${path}.width must equal x1 - x0`);
    if (room.height != null && Math.abs(room.height - (room.y1 - room.y0)) > 0.01) errors.push(`${path}.height must equal y1 - y0`);
    if (room.width_real != null && Math.abs(room.width_real - (room.x1 - room.x0) / 20) > 0.01) errors.push(`${path}.width_real must use 20 px per ft`);
    if (room.height_real != null && Math.abs(room.height_real - (room.y1 - room.y0) / 20) > 0.01) errors.push(`${path}.height_real must use 20 px per ft`);
    if (!['filled', 'walls_only'].includes(room.fill_mode)) errors.push(`${path}.fill_mode must be filled or walls_only`);
    if (room.wall_thickness_ft != null) finite(room.wall_thickness_ft, `${path}.wall_thickness_ft`, errors, 0.05, 3);
    validateFlooring(room.flooring, `${path}.flooring`, errors);

    if (room.wall_erased_regions != null) {
      if (!object(room.wall_erased_regions)) errors.push(`${path}.wall_erased_regions must be an object`);
      else for (const [side, intervals] of Object.entries(room.wall_erased_regions)) {
        if (!SIDES.has(side)) { errors.push(`${path}.wall_erased_regions.${side} is not a valid side`); continue; }
        if (!Array.isArray(intervals) || intervals.length > 12) { errors.push(`${path}.wall_erased_regions.${side} must be an array of at most 12 intervals`); continue; }
        const min = side === 'top' || side === 'bottom' ? room.x0 : room.y0;
        const max = side === 'top' || side === 'bottom' ? room.x1 : room.y1;
        let prior = min;
        intervals.forEach((interval, gapIndex) => {
          const gapPath = `${path}.wall_erased_regions.${side}[${gapIndex}]`;
          if (!Array.isArray(interval) || interval.length !== 2) return errors.push(`${gapPath} must be [start, end]`);
          if (!finite(interval[0], `${gapPath}[0]`, errors, min, max) || !finite(interval[1], `${gapPath}[1]`, errors, min, max)) return;
          if (interval[1] <= interval[0]) errors.push(`${gapPath} must have positive length`);
          if (interval[0] < prior) errors.push(`${gapPath} overlaps or is unsorted`);
          prior = interval[1];
          const segment = side === 'top' || side === 'bottom'
            ? [interval[0], side === 'top' ? room.y0 : room.y1, interval[1], side === 'top' ? room.y0 : room.y1]
            : [side === 'left' ? room.x0 : room.x1, interval[0], side === 'left' ? room.x0 : room.x1, interval[1]];
          if (interval[0] > min || interval[1] < max) gaps.push(segment);
        });
      }
    }
  });

  for (let i = 0; i < rooms.length; i++) for (let j = i + 1; j < rooms.length; j++) {
    const a = rooms[i], b = rooms[j];
    if (!object(a) || !object(b)) continue;
    const overlap = Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));
    const smaller = Math.min((a.x1 - a.x0) * (a.y1 - a.y0), (b.x1 - b.x0) * (b.y1 - b.y0));
    if (overlap > Math.max(4, smaller * 0.02)) errors.push(`rooms[${i}] and rooms[${j}] substantially overlap`);
  }

  let pointCount = 0;
  shapes.forEach((shape, index) => {
    const path = `shapes[${index}]`;
    addId(shape, path);
    if (!object(shape)) return;
    if (!SHAPES.has(shape.type)) errors.push(`${path}.type must be line or polygon`);
    const points = collection(shape.points, `${path}.points`, errors, 64);
    pointCount += points.length;
    const validPoints = points.map((p, pointIndex) => point(p, `${path}.points[${pointIndex}]`, errors, width, height));
    if (shape.type === 'line' && points.length !== 2) errors.push(`${path}.line must have exactly 2 points`);
    if (shape.type === 'line' && points.length === 2 && validPoints.every(Boolean) && points[0][0] === points[1][0] && points[0][1] === points[1][1]) errors.push(`${path}.line must have nonzero length`);
    if (shape.type === 'polygon') {
      if (points.length < 3) errors.push(`${path}.polygon must have at least 3 points`);
      if (points.length >= 3 && validPoints.every(Boolean)) {
        const area2 = points.reduce((sum, p, i) => sum + p[0] * points[(i + 1) % points.length][1] - points[(i + 1) % points.length][0] * p[1], 0);
        if (Math.abs(area2) < 2) errors.push(`${path}.polygon must have nonzero area`);
      }
      const tags = Array.isArray(shape.tags) ? shape.tags : [];
      const group = tags.find((tag) => typeof tag === 'string' && tag.startsWith('polygon_group_'));
      if (!group) errors.push(`${path}.polygon requires a polygon_group_ tag`);
      else if (polygonTags.has(group)) errors.push(`${path} polygon group tag must be unique`);
      else polygonTags.add(group);
      validateFlooring(shape.flooring, `${path}.flooring`, errors);
    }
    if (!Array.isArray(shape.tags) || shape.tags.length > 20 || shape.tags.some((tag) => typeof tag !== 'string' || tag.length > 100)) errors.push(`${path}.tags is invalid`);
    if (shape.width != null) finite(shape.width, `${path}.width`, errors, 0.1, 50);
  });
  if (pointCount > MAX_POINTS) errors.push(`shapes exceed ${MAX_POINTS} points`);
  if (rooms.length === 0 && !shapes.some((shape) => object(shape) && shape.type === 'polygon')) errors.push('layout must contain at least one room');

  furniture.forEach((item, index) => {
    const path = `furniture[${index}]`;
    addId(item, path);
    if (!object(item)) return;
    if (!FURNITURE.has(item.image_name)) errors.push(`${path}.image_name is unsupported`);
    finite(item.x, `${path}.x`, errors, 0, width);
    finite(item.y, `${path}.y`, errors, 0, height);
    if (item.scale != null) finite(item.scale, `${path}.scale`, errors, 0.1, 10);
    if (item.angle != null) finite(item.angle, `${path}.angle`, errors, -3_600, 3_600);
    if (/door/i.test(String(item.image_name))) {
      const nearGap = gaps.some(([x0, y0, x1, y1]) => distanceToSegment(item.x, item.y, x0, y0, x1, y1) <= 45);
      if (!nearGap) errors.push(`${path} door must be within 45 canvas pixels of a partial wall gap`);
    }
  });

  texts.forEach((item, index) => {
    const path = `text[${index}]`;
    addId(item, path);
    if (!object(item)) return;
    string(item.content, `${path}.content`, errors, 500);
    finite(item.x, `${path}.x`, errors, 0, width);
    finite(item.y, `${path}.y`, errors, 0, height);
    if (item.font != null && (typeof item.font !== 'string' || item.font.length > 100)) errors.push(`${path}.font is invalid`);
    if (item.tags != null && (!Array.isArray(item.tags) || item.tags.length > 20 || item.tags.some((tag) => typeof tag !== 'string' || tag.length > 100))) errors.push(`${path}.tags must be an array of at most 20 strings, for example ["user_text"], or be omitted`);
  });

  if (layout.compass != null) {
    if (!object(layout.compass)) errors.push('compass must be an object');
    else {
      if (layout.compass.direction != null && !['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'].includes(layout.compass.direction)) errors.push('compass.direction is invalid');
      if (layout.compass.north_deg_clockwise != null) finite(layout.compass.north_deg_clockwise, 'compass.north_deg_clockwise', errors, 0, 359.999999);
      if (layout.compass.direction == null && layout.compass.north_deg_clockwise == null) errors.push('compass requires direction or north_deg_clockwise');
    }
  }
  return { ok: errors.length === 0, errors: [...new Set(errors)].slice(0, 40) };
}

export function assertValidLayout(layout) {
  const result = validateLayout(layout);
  if (!result.ok) throw Object.assign(new Error(result.errors.join('; ')), { validationErrors: result.errors });
  return layout;
}

if (process.argv[1] && import.meta.url === new URL(`file:///${process.argv[1].replaceAll('\\', '/')}`).href) {
  const { readFile } = await import('node:fs/promises');
  const file = process.argv[2];
  if (!file) throw new Error('Usage: node server/validator.mjs <layout.json>');
  const result = validateLayout(JSON.parse(await readFile(file, 'utf8')));
  if (!result.ok) { console.error(result.errors.join('\n')); process.exitCode = 1; }
  else console.log('Valid Vastu v1 layout');
}