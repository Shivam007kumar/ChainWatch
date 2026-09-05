export const STATE_COORDS = {
  Maharashtra: [75.7139, 19.7515], Delhi: [77.1025, 28.7041], Karnataka: [75.7139, 15.3173],
  Gujarat: [71.1924, 22.2587], 'Tamil Nadu': [78.6569, 11.1271], 'West Bengal': [87.8550, 22.9868],
  'Uttar Pradesh': [80.9462, 26.8467], Telangana: [79.0193, 18.1124], Kerala: [76.2711, 10.8505],
  Rajasthan: [74.2179, 27.0238], Manipur: [93.9063, 24.6637], Goa: [74.1240, 15.2993],
  'Jammu and Kashmir': [76.5762, 33.7782], Ladakh: [77.5770, 34.1526]
};

function coordinatePairs(value, pairs = []) {
  if (Array.isArray(value)) {
    if (typeof value[0] === 'number' && typeof value[1] === 'number') {
      pairs.push(value);
    } else {
      value.forEach(item => coordinatePairs(item, pairs));
    }
  }
  return pairs;
}

function pointInRing(point, ring) {
  let inside = false;
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x, y] = ring[index];
    const [previousX, previousY] = ring[previous];
    const intersects = ((y > point[1]) !== (previousY > point[1]))
      && point[0] < ((previousX - x) * (point[1] - y)) / (previousY - y) + x;
    if (intersects) inside = !inside;
  }
  return inside;
}

function pointInGeometry(point, geometry) {
  if (!geometry) return false;
  if (geometry.type === 'Polygon') {
    return pointInRing(point, geometry.coordinates[0])
      && !geometry.coordinates.slice(1).some(ring => pointInRing(point, ring));
  }
  if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates.some(polygon => pointInGeometry(point, { type: 'Polygon', coordinates: polygon }));
  }
  return false;
}

export function getStateCenter(stateName, geoJson) {
  const features = geoJson.features.filter(feature => {
    const name = feature.properties.st_nm || feature.properties.name || feature.properties.NAME_1;
    return name?.toLowerCase() === stateName?.toLowerCase();
  });
  const coordinateList = features.flatMap(feature => coordinatePairs(feature.geometry.coordinates));
  if (!coordinateList.length) return STATE_COORDS[stateName] || [80, 22];

  const longitudes = coordinateList.map(([longitude]) => longitude);
  const latitudes = coordinateList.map(([, latitude]) => latitude);
  return [
    (Math.min(...longitudes) + Math.max(...longitudes)) / 2,
    (Math.min(...latitudes) + Math.max(...latitudes)) / 2
  ];
}

export function getWalletDots(wallets, geoJson) {
  let randomState = 1;
  const nextRandom = () => {
    randomState = (randomState * 1664525 + 1013904223) % 4294967296;
    return randomState / 4294967296;
  };

  const groupedWallets = wallets.reduce((groups, wallet) => {
    const stateName = wallet.primary_state || 'Unknown';
    groups[stateName] = groups[stateName] || [];
    groups[stateName].push(wallet);
    return groups;
  }, {});

  return Object.entries(groupedWallets).flatMap(([stateName, stateWallets]) => {
    const features = geoJson.features.filter(feature => {
      const name = feature.properties.st_nm || feature.properties.name || feature.properties.NAME_1;
      return name?.toLowerCase() === stateName.toLowerCase();
    });
    const coordinateList = features.flatMap(feature => coordinatePairs(feature.geometry.coordinates));
    if (!coordinateList.length) return [];

    const longitudes = coordinateList.map(([longitude]) => longitude);
    const latitudes = coordinateList.map(([, latitude]) => latitude);
    const bounds = {
      minLongitude: Math.min(...longitudes), maxLongitude: Math.max(...longitudes),
      minLatitude: Math.min(...latitudes), maxLatitude: Math.max(...latitudes)
    };

    return stateWallets.map((wallet, index) => {
      let point;
      let attempts = 0;
      do {
        point = [
          bounds.minLongitude + nextRandom() * (bounds.maxLongitude - bounds.minLongitude),
          bounds.minLatitude + nextRandom() * (bounds.maxLatitude - bounds.minLatitude)
        ];
        attempts += 1;
      } while (attempts < 10000 && !features.some(feature => pointInGeometry(point, feature.geometry)));

      if (!features.some(feature => pointInGeometry(point, feature.geometry))) return null;
      const confidence = Number(wallet.confidence_score) || 0;
      return {
        id: wallet.wallet_address,
        lng: point[0],
        lat: point[1],
        wallet: wallet.wallet_address,
        state: stateName,
        confidence,
        color: wallet.is_threat ? (confidence >= 85 ? '#e86a6a' : '#e9a24f') : '#4f8fc9'
      };
    });
  }).filter(Boolean);
}

export function generateStateDots(stateName, count, geoJson) {
  const features = geoJson.features.filter(feature => {
    const name = feature.properties.st_nm || feature.properties.name || feature.properties.NAME_1;
    return name?.toLowerCase() === stateName?.toLowerCase();
  });
  const coordinateList = features.flatMap(feature => coordinatePairs(feature.geometry.coordinates));
  if (!coordinateList.length) {
    const base = STATE_COORDS[stateName] || [80, 22];
    return Array.from({ length: count }, (_, id) => ({ id, lng: base[0], lat: base[1] }));
  }

  const longitudes = coordinateList.map(([longitude]) => longitude);
  const latitudes = coordinateList.map(([, latitude]) => latitude);
  const bounds = {
    minLongitude: Math.min(...longitudes), maxLongitude: Math.max(...longitudes),
    minLatitude: Math.min(...latitudes), maxLatitude: Math.max(...latitudes)
  };
  const dots = [];
  let attempts = 0;
  while (dots.length < count && attempts < count * 10000) {
    attempts += 1;
    const point = [
      bounds.minLongitude + Math.random() * (bounds.maxLongitude - bounds.minLongitude),
      bounds.minLatitude + Math.random() * (bounds.maxLatitude - bounds.minLatitude)
    ];
    if (features.some(feature => pointInGeometry(point, feature.geometry))) {
      dots.push({ id: dots.length, lng: point[0], lat: point[1] });
    }
  }
  return dots;
}

export function generateAllStateDots(geoJson, countPerState = 3) {
  const stateNames = [...new Set(geoJson.features.map(feature => (
    feature.properties.st_nm || feature.properties.name || feature.properties.NAME_1
  )).filter(Boolean))];

  return stateNames.flatMap(stateName => generateStateDots(stateName, countPerState, geoJson));
}
