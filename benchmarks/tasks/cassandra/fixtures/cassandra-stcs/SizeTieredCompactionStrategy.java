/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.cassandra.db.compaction;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.apache.cassandra.db.ColumnFamilyStore;
import org.apache.cassandra.db.lifecycle.LifecycleTransaction;
import org.apache.cassandra.exceptions.ConfigurationException;
import org.apache.cassandra.io.sstable.format.SSTableReader;
import org.apache.cassandra.schema.CompactionParams;

/**
 * Implements Size-Tiered Compaction Strategy (STCS) for Apache Cassandra.
 *
 * SizeTieredCompactionStrategy groups SSTables into buckets by approximate
 * size and compacts buckets that reach the minimum threshold. This is the
 * default compaction strategy and performs best for write-heavy workloads
 * with infrequent reads, such as time-series data ingestion.
 *
 * Configuration options are managed by {@link SizeTieredCompactionStrategyOptions}.
 */
public class SizeTieredCompactionStrategy extends AbstractCompactionStrategy
{
    private static final Logger logger = LoggerFactory.getLogger(SizeTieredCompactionStrategy.class);

    private final SizeTieredCompactionStrategyOptions sizeTieredOptions;

    public SizeTieredCompactionStrategy(ColumnFamilyStore cfs, Map<String, String> options)
    {
        super(cfs, options);
        this.sizeTieredOptions = new SizeTieredCompactionStrategyOptions(options);
    }

    /**
     * Returns the next compaction task for SizeTieredCompactionStrategy, or null
     * if no compaction candidates meet the minimum threshold.
     *
     * SizeTieredCompactionStrategy selects the largest eligible bucket whose
     * SSTable count meets or exceeds {@code min_threshold}.
     */
    @Override
    public AbstractCompactionTask getNextBackgroundTask(int gcBefore)
    {
        List<SSTableReader> candidates = new ArrayList<>(cfs.getUncompactingSSTables());
        if (candidates.isEmpty())
            return null;

        List<List<SSTableReader>> buckets = getBuckets(
            candidates,
            sizeTieredOptions.bucketLow,
            sizeTieredOptions.bucketHigh,
            sizeTieredOptions.minSSTableSize
        );
        List<SSTableReader> sstables = getNextBackgroundSSTables(buckets, gcBefore);
        if (sstables == null)
            return null;

        LifecycleTransaction transaction = cfs.getTracker().tryModify(sstables, OperationType.COMPACTION);
        return transaction == null ? null : new CompactionTask(cfs, transaction, gcBefore);
    }

    /**
     * Groups the provided SSTables into size-tiered buckets for
     * SizeTieredCompactionStrategy compaction candidate selection.
     *
     * @param files       candidate SSTables to bucket
     * @param bucketLow   lower size ratio for bucket membership
     * @param bucketHigh  upper size ratio for bucket membership
     * @param minSSTableSize minimum SSTable size to consider
     * @return list of buckets, each bucket being a list of similarly-sized SSTables
     */
    public static List<List<SSTableReader>> getBuckets(Collection<SSTableReader> files,
                                                        double bucketLow,
                                                        double bucketHigh,
                                                        long minSSTableSize)
    {
        List<SSTableReader> sortedFiles = new ArrayList<>(files);
        sortedFiles.sort((a, b) -> Long.compare(a.onDiskLength(), b.onDiskLength()));

        Map<Long, List<SSTableReader>> buckets = new HashMap<>();
        for (SSTableReader sstable : sortedFiles)
        {
            long size = Math.max(sstable.onDiskLength(), minSSTableSize);
            boolean added = false;
            for (Map.Entry<Long, List<SSTableReader>> entry : buckets.entrySet())
            {
                long bucketAverage = entry.getKey();
                if (size > bucketAverage * bucketLow && size < bucketAverage * bucketHigh)
                {
                    entry.getValue().add(sstable);
                    added = true;
                    break;
                }
            }
            if (!added)
            {
                List<SSTableReader> newBucket = new ArrayList<>();
                newBucket.add(sstable);
                buckets.put(size, newBucket);
            }
        }
        return new ArrayList<>(buckets.values());
    }

    private List<SSTableReader> getNextBackgroundSSTables(List<List<SSTableReader>> buckets, int gcBefore)
    {
        for (List<SSTableReader> bucket : buckets)
        {
            if (bucket.size() >= sizeTieredOptions.minThreshold)
                return bucket;
        }
        return null;
    }

    public static Map<String, String> validateOptions(Map<String, String> options)
        throws ConfigurationException
    {
        Map<String, String> unchecked = AbstractCompactionStrategy.validateOptions(options);
        return SizeTieredCompactionStrategyOptions.validateOptions(options, unchecked);
    }
}
