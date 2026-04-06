import {IEntity} from "./IEntity.ts";

export interface IReduxState<T extends IEntity> {
    loading: boolean;
    updating: boolean;
    updateState: boolean;
    response: null | any; // Replace 'any' with the actual response type if known
    error: null | any;    // Replace 'any' with the actual error type if known
    entity: T;
    entities: ReadonlyArray<T>;
    currentPage: number,
    numberOfPages: number,
}