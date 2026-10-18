import {describe,it,expect} from 'vitest';
import {matchesCollection} from './CollectionFilters';
const none={query:'',status:'',from:'',to:''};
describe('collection filtering',()=>{
 it('combines all words, status and inclusive date limits',()=>{
   const f={query:'wheat water',status:'Open',from:'2026-10-18',to:'2026-10-20'};
   expect(matchesCollection('Water the Wheat','Open','2026-10-20T13:00:00Z',f)).toBe(true);
   expect(matchesCollection('Water the Wheat','Completed','2026-10-20',f)).toBe(false);
   expect(matchesCollection('Water the Wheat','Open','2026-10-21',f)).toBe(false);
 });
 it('keeps undated records until a date restriction is selected',()=>{
   expect(matchesCollection('Farm','', '',none)).toBe(true);
   expect(matchesCollection('Farm','', '',{...none,from:'2026-10-18'})).toBe(false);
   expect(matchesCollection('Farm','', '',{...none,query:'missing'})).toBe(false);
 });
});
