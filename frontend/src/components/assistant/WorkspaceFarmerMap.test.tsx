import { describe, expect, it, vi } from 'vitest';
vi.mock('./MitraHelper', () => ({MitraHelper: () => null}));
import { filterMapFarmers, normalizeMapFarmers, nearbyMapFarmers } from './WorkspaceFarmerMap';
describe('farmer map directory', () => {
  it('handles nullable profiles and numeric database coordinates without losing zero coordinates', () => {
    const farmers = normalizeMapFarmers([{id:'a', name:'Asha', latitude:'0', longitude:'73.2', crops:null, excess_resources:null}, {id:'b', latitude:null, longitude:500}]);
    expect(farmers[0].latitude).toBe(0);
    expect(farmers[0].longitude).toBe(73.2);
    expect(farmers[1].latitude).toBeNull();
    expect(farmers[1].longitude).toBeNull();
    expect(filterMapFarmers(farmers, 'asha')).toHaveLength(1);
  });
  it('finds farmers by resource, crop and location together, including needs', () => {
    const farmers = normalizeMapFarmers([{id:'a',name:'Asha',state:'Maharashtra',crops:['Wheat'],required_resources:['Tractor'],excess_resources:['Pump']}]);
    expect(filterMapFarmers(farmers, 'maharashtra tractor')).toHaveLength(1);
    expect(filterMapFarmers(farmers, 'wheat pump')).toHaveLength(1);
    expect(filterMapFarmers(farmers, 'rice')).toHaveLength(0);
  });
});

describe('nearby farmer list', () => {
  const farmers = normalizeMapFarmers([
    {id:'far', name:'Far', latitude:28, longitude:78},
    {id:'near', name:'Near', latitude:19.1, longitude:73.1},
    {id:'mid', name:'Middle', latitude:20, longitude:74},
    {id:'unknown', name:'Unknown', latitude:null, longitude:null},
  ]);
  it('only lists farmers inside the current map area, nearest centre first', () => {
    expect(nearbyMapFarmers(farmers, {south:18,north:22,west:72,east:76,lat:19,lng:73}).map(f => f.id)).toEqual(['near','mid']);
  });
  it('updates the nearest order when the map moves and handles empty views', () => {
    expect(nearbyMapFarmers(farmers, {south:18,north:30,west:72,east:80,lat:28,lng:78})[0].id).toBe('far');
    expect(nearbyMapFarmers(farmers, {south:0,north:1,west:0,east:1,lat:0,lng:0})).toEqual([]);
    expect(nearbyMapFarmers(farmers, null)).toEqual([]);
  });
});
