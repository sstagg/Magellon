import React from "react";

const InfoCards = ({ defocus1, defocus2, angleAstigmatism, resolution50Percent }) => {
    // Convert values
    const defocus1Micrometers = (defocus1 * 1e6).toFixed(2); // Defocus 1 in μm
    const defocus2Micrometers = (defocus2 * 1e6).toFixed(2); // Defocus 2 in μm
    const angleAstigmatismDegrees = (angleAstigmatism * (180 / Math.PI)).toFixed(2); // Angle astigmatism in °
    const resolutionAngstroms = resolution50Percent.toFixed(2); // Resolution 50% in Å

    return (
        <div className="bg-gray-200 h-screen w-full dark:bg-gray-700 flex justify-center items-center">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:py-24 lg:px-8">
                <h2 className="text-3xl font-extrabold tracking-tight text-gray-900 sm:text-4xl dark:text-white">
                    Our service statistics
                </h2>
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-4 mt-4">
                    {/* Defocus 1 */}
                    <div className="bg-white overflow-hidden shadow sm:rounded-lg dark:bg-gray-900">
                        <div className="px-4 py-5 sm:p-6">
                            <dl>
                                <dt className="text-sm leading-5 font-medium text-gray-500 truncate dark:text-gray-400">Defocus 1</dt>
                                <dd className="mt-1 text-3xl leading-9 font-semibold text-indigo-600 dark:text-indigo-400">
                                    {defocus1Micrometers} μm
                                </dd>
                            </dl>
                        </div>
                    </div>

                    {/* Defocus 2 */}
                    <div className="bg-white overflow-hidden shadow sm:rounded-lg dark:bg-gray-900">
                        <div className="px-4 py-5 sm:p-6">
                            <dl>
                                <dt className="text-sm leading-5 font-medium text-gray-500 truncate dark:text-gray-400">Defocus 2</dt>
                                <dd className="mt-1 text-3xl leading-9 font-semibold text-indigo-600 dark:text-indigo-400">
                                    {defocus2Micrometers} μm
                                </dd>
                            </dl>
                        </div>
                    </div>

                    {/* Angle Astigmatism */}
                    <div className="bg-white overflow-hidden shadow sm:rounded-lg dark:bg-gray-900">
                        <div className="px-4 py-5 sm:p-6">
                            <dl>
                                <dt className="text-sm leading-5 font-medium text-gray-500 truncate dark:text-gray-400">Angle Astigmatism</dt>
                                <dd className="mt-1 text-3xl leading-9 font-semibold text-indigo-600 dark:text-indigo-400">
                                    {angleAstigmatismDegrees} °
                                </dd>
                            </dl>
                        </div>
                    </div>

                    {/* Resolution 50% */}
                    <div className="bg-white overflow-hidden shadow sm:rounded-lg dark:bg-gray-900">
                        <div className="px-4 py-5 sm:p-6">
                            <dl>
                                <dt className="text-sm leading-5 font-medium text-gray-500 truncate dark:text-gray-400">Resolution 50%</dt>
                                <dd className="mt-1 text-3xl leading-9 font-semibold text-indigo-600 dark:text-indigo-400">
                                    {resolutionAngstroms} Å
                                </dd>
                            </dl>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default InfoCards;
