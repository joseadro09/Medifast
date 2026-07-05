import { TestBed } from '@angular/core/testing';

import { Logistica } from './logistica';

describe('Logistica', () => {
  let service: Logistica;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(Logistica);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
