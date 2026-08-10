import { useCallback, useEffect, useState } from 'react'

import { acceptPrediction, acceptPredictions, cancelPrediction, editPrediction, fetchImagePredictions, fetchModels, fetchPredictionStatus, predictionEventsUrl, rejectPrediction, startPrediction } from '../api/client'

const activeStates = new Set(['PREPARING','RUNNING'])

export function usePredictions(projectId, imageId, onAnnotationsChanged) {
  const [models,setModels]=useState([]), [modelId,setModelId]=useState(''), [predictions,setPredictions]=useState([]), [job,setJob]=useState(null), [logs,setLogs]=useState([]), [error,setError]=useState('')
  const loadPredictions=useCallback(async()=>{ if(!imageId||!modelId){setPredictions([]);return} try{const result=await fetchImagePredictions(imageId,modelId);setPredictions(result.predictions);setError('')}catch(requestError){setError(requestError.message)} },[imageId,modelId])
  useEffect(()=>{let active=true; Promise.all([fetchModels(),fetchPredictionStatus()]).then(([available,status])=>{if(!active)return;setModels(available);setModelId(current=>available.some(item=>item.id===current)?current:(available[0]?.id||''));setJob(status.job)}).catch(error=>{if(active)setError(error.message)});return()=>{active=false}},[projectId])
  useEffect(()=>{let active=true;if(!imageId||!modelId){queueMicrotask(()=>{if(active)setPredictions([])});return()=>{active=false}}fetchImagePredictions(imageId,modelId).then(result=>{if(active){setPredictions(result.predictions);setError('')}}).catch(requestError=>{if(active)setError(requestError.message)});return()=>{active=false}},[imageId,modelId])
  useEffect(()=>{if(!job?.id)return undefined;const source=new EventSource(predictionEventsUrl(job.id));const add=(event)=>{const entry=JSON.parse(event.data);setLogs(current=>[...current,entry].slice(-1000));if(entry.data)setJob(current=>current?{...current,...entry.data}:current)};source.addEventListener('log',add);source.addEventListener('progress',add);source.addEventListener('status',(event)=>{const payload=JSON.parse(event.data);setJob(payload.job);source.close();loadPredictions()});source.onerror=()=>{};return()=>source.close()},[job?.id,loadPredictions])
  const run=async(mode,confidence,maxDetections)=>{setError('');setLogs([]);try{const created=await startPrediction({model_id:modelId,mode,image_id:mode==='current'?imageId:null,confidence_threshold:confidence,max_detections:maxDetections});setJob(created);return true}catch(requestError){setError(requestError.message);return false}}
  const update=async(id,data)=>{try{const record=await editPrediction(id,data);setPredictions(current=>current.map(item=>item.id===id?record:item));return true}catch(requestError){setError(requestError.message);return false}}
  const reject=async(id)=>{try{await rejectPrediction(id);setPredictions(current=>current.filter(item=>item.id!==id));return true}catch(requestError){setError(requestError.message);return false}}
  const accept=async(ids)=>{try{if(ids.length===1)await acceptPrediction(ids[0]);else await acceptPredictions(ids);setPredictions(current=>current.filter(item=>!ids.includes(item.id)));await onAnnotationsChanged?.();return true}catch(requestError){setError(requestError.message);return false}}
  const cancel=async()=>{if(job&&activeStates.has(job.state))try{await cancelPrediction(job.id)}catch(requestError){setError(requestError.message)}}
  return {models,modelId,setModelId,predictions,setPredictions,job,logs,error,running:Boolean(job&&activeStates.has(job.state)),run,update,reject,accept,cancel,refresh:loadPredictions}
}
