import { describe, expect, it, vi } from 'vitest';
vi.mock('./MitraHelper', () => ({MitraHelper: () => null}));
import { filterMapFarmers, normalizeMapFarmers } from './WorkspaceFarmerMap';
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
