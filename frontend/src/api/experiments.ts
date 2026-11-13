import {request} from './client';
import {Experiment} from '../types/domain';

export type ExperimentDraft=Omit<Experiment,'id'|'owner'>;

export const getExperiments=()=>request<Experiment[]>('/experiments');
export const createExperiment=(data:ExperimentDraft)=>request<Experiment>('/experiments',{method:'POST',body:JSON.stringify(data)});
